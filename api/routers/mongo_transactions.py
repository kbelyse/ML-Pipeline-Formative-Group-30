"""CRUD and time-series endpoints backed by MongoDB."""
from datetime import date

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, Response
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pydantic import ValidationError

from api.mongo_db import transactions
from api.schemas import DailySummary, TransactionIn, TransactionOut, TransactionUpdate
from api.utils import date_bounds

router = APIRouter(prefix="/mongo", tags=["MongoDB"])


def to_document(data: TransactionIn) -> dict:
    return {
        "invoice_no": data.invoice_no,
        "invoice_date": data.invoice_date,
        "is_cancelled": data.invoice_no.upper().startswith("C"),
        "customer": {"customer_id": data.customer_id, "country": data.country},
        "product": {"stock_code": data.stock_code, "description": data.description},
        "quantity": data.quantity,
        "unit_price": data.unit_price,
        "revenue": round(data.quantity * data.unit_price, 3),
    }


def to_out(doc: dict) -> TransactionOut:
    return TransactionOut(
        id=str(doc["_id"]), invoice_no=doc["invoice_no"],
        stock_code=doc["product"]["stock_code"], description=doc["product"]["description"],
        quantity=doc["quantity"], invoice_date=doc["invoice_date"],
        unit_price=doc["unit_price"], customer_id=doc["customer"]["customer_id"],
        country=doc["customer"]["country"], is_cancelled=doc["is_cancelled"],
        revenue=doc["revenue"],
    )


def parse_id(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"'{doc_id}' is not a valid MongoDB id")


def get_doc(doc_id: str) -> dict:
    doc = transactions.find_one({"_id": parse_id(doc_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Transaction {doc_id} not found")
    return doc


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn):
    doc = to_document(data)
    doc["_id"] = transactions.insert_one(doc).inserted_id
    return to_out(doc)


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    cursor = transactions.find().sort("_id", ASCENDING).skip(offset).limit(limit)
    return [to_out(doc) for doc in cursor]


@router.get("/transactions/latest", response_model=TransactionOut)
def latest_transaction():
    doc = transactions.find_one(sort=[("invoice_date", DESCENDING), ("_id", DESCENDING)])
    if doc is None:
        raise HTTPException(status_code=404, detail="No transactions stored")
    return to_out(doc)


@router.get("/transactions/range", response_model=list[TransactionOut])
def transactions_by_date_range(start: date, end: date,
                               limit: int = Query(100_000, ge=1, le=600_000)):
    low, high = date_bounds(start, end)
    cursor = (transactions.find({"invoice_date": {"$gte": low, "$lt": high}})
              .sort([("invoice_date", ASCENDING), ("_id", ASCENDING)]).limit(limit))
    return [to_out(doc) for doc in cursor]


@router.get("/transactions/{doc_id}", response_model=TransactionOut)
def get_transaction(doc_id: str):
    return to_out(get_doc(doc_id))


@router.put("/transactions/{doc_id}", response_model=TransactionOut)
def update_transaction(doc_id: str, changes: TransactionUpdate):
    current = to_out(get_doc(doc_id)).model_dump(exclude={"id", "is_cancelled", "revenue"})
    try:
        data = TransactionIn(**{**current, **changes.model_dump(exclude_unset=True)})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False, include_context=False, include_input=False))
    doc = transactions.find_one_and_update({"_id": parse_id(doc_id)}, {"$set": to_document(data)},
                                           return_document=ReturnDocument.AFTER)
    return to_out(doc)


@router.delete("/transactions/{doc_id}", status_code=204)
def delete_transaction(doc_id: str):
    if transactions.delete_one({"_id": parse_id(doc_id)}).deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Transaction {doc_id} not found")
    return Response(status_code=204)


@router.get("/daily", response_model=list[DailySummary])
def daily_summary(start: date, end: date):
    """Daily revenue series for a date range, aggregated in MongoDB."""
    low, high = date_bounds(start, end)
    pipeline = [
        {"$match": {"invoice_date": {"$gte": low, "$lt": high}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$invoice_date"}},
            "gross_revenue": {"$sum": {"$cond": ["$is_cancelled", 0, "$revenue"]}},
            "net_revenue": {"$sum": "$revenue"},
            "invoices": {"$addToSet": {"$cond": ["$is_cancelled", None, "$invoice_no"]}},
            "total_quantity": {"$sum": {"$cond": ["$is_cancelled", 0, "$quantity"]}},
            "n_lines": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0, "date": "$_id", "gross_revenue": 1, "net_revenue": 1,
            "total_quantity": 1, "n_lines": 1,
            "n_invoices": {"$size": {"$filter": {"input": "$invoices", "cond": {"$ne": ["$$this", None]}}}},
        }},
        {"$sort": {"date": 1}},
    ]
    return [DailySummary(**row) for row in transactions.aggregate(pipeline)]

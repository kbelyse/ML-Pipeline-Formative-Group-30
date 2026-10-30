"""CRUD and time-series endpoints backed by MySQL."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from api.schemas import DailySummary, TransactionIn, TransactionOut, TransactionUpdate
from api.sql_db import Country, Customer, Invoice, InvoiceLine, Product, get_session
from api.utils import date_bounds

router = APIRouter(prefix="/sql", tags=["MySQL"])


def to_out(line: InvoiceLine) -> TransactionOut:
    inv = line.invoice
    price = float(line.unit_price)
    return TransactionOut(
        id=line.line_id, invoice_no=inv.invoice_no, stock_code=line.stock_code,
        description=line.product.description, quantity=line.quantity,
        invoice_date=inv.invoice_date, unit_price=price, customer_id=inv.customer_id,
        country=inv.country.name, is_cancelled=inv.is_cancelled,
        revenue=round(line.quantity * price, 3),
    )


def base_query():
    return select(InvoiceLine).join(InvoiceLine.invoice).options(
        joinedload(InvoiceLine.invoice).joinedload(Invoice.country),
        joinedload(InvoiceLine.product),
    )


def get_line(session: Session, line_id: int) -> InvoiceLine:
    line = session.scalars(base_query().where(InvoiceLine.line_id == line_id)).first()
    if line is None:
        raise HTTPException(status_code=404, detail=f"Transaction {line_id} not found")
    return line


def upsert_parents(session: Session, data: TransactionIn) -> None:
    """Create the country, customer, product and invoice rows a line depends on."""
    country = session.scalars(select(Country).where(Country.name == data.country)).first()
    if country is None:
        country = Country(name=data.country)
        session.add(country)
        session.flush()

    if session.get(Customer, data.customer_id) is None:
        session.add(Customer(customer_id=data.customer_id))

    product = session.get(Product, data.stock_code)
    if product is None:
        session.add(Product(stock_code=data.stock_code, description=data.description))
    elif data.description:
        product.description = data.description

    # Invoice-level fields (date, customer, country) are shared by all lines of the invoice
    invoice = session.get(Invoice, data.invoice_no)
    if invoice is None:
        invoice = Invoice(invoice_no=data.invoice_no)
        session.add(invoice)
    invoice.invoice_date = data.invoice_date
    invoice.customer_id = data.customer_id
    invoice.country_id = country.country_id
    invoice.is_cancelled = data.invoice_no.upper().startswith("C")
    session.flush()


def delete_invoice_if_empty(session: Session, invoice_no: str) -> None:
    remaining = session.scalar(select(func.count()).where(InvoiceLine.invoice_no == invoice_no))
    if remaining == 0:
        session.delete(session.get(Invoice, invoice_no))


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, session: Session = Depends(get_session)):
    upsert_parents(session, data)
    line = InvoiceLine(invoice_no=data.invoice_no, stock_code=data.stock_code,
                       quantity=data.quantity, unit_price=data.unit_price)
    session.add(line)
    session.commit()
    return to_out(get_line(session, line.line_id))


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
                      session: Session = Depends(get_session)):
    stmt = base_query().order_by(InvoiceLine.line_id).limit(limit).offset(offset)
    return [to_out(line) for line in session.scalars(stmt)]


@router.get("/transactions/latest", response_model=TransactionOut)
def latest_transaction(session: Session = Depends(get_session)):
    stmt = base_query().order_by(Invoice.invoice_date.desc(), InvoiceLine.line_id.desc()).limit(1)
    line = session.scalars(stmt).first()
    if line is None:
        raise HTTPException(status_code=404, detail="No transactions stored")
    return to_out(line)


@router.get("/transactions/range", response_model=list[TransactionOut])
def transactions_by_date_range(start: date, end: date,
                               limit: int = Query(100_000, ge=1, le=600_000),
                               session: Session = Depends(get_session)):
    low, high = date_bounds(start, end)
    stmt = (base_query()
            .where(Invoice.invoice_date >= low, Invoice.invoice_date < high)
            .order_by(Invoice.invoice_date, InvoiceLine.line_id).limit(limit))
    return [to_out(line) for line in session.scalars(stmt)]


@router.get("/transactions/{line_id}", response_model=TransactionOut)
def get_transaction(line_id: int, session: Session = Depends(get_session)):
    return to_out(get_line(session, line_id))


@router.put("/transactions/{line_id}", response_model=TransactionOut)
def update_transaction(line_id: int, changes: TransactionUpdate,
                       session: Session = Depends(get_session)):
    line = get_line(session, line_id)
    current = to_out(line).model_dump(exclude={"id", "is_cancelled", "revenue"})
    try:
        data = TransactionIn(**{**current, **changes.model_dump(exclude_unset=True)})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False, include_context=False, include_input=False))

    old_invoice = line.invoice_no
    upsert_parents(session, data)
    line.invoice_no = data.invoice_no
    line.stock_code = data.stock_code
    line.quantity = data.quantity
    line.unit_price = data.unit_price
    session.flush()
    if old_invoice != data.invoice_no:
        delete_invoice_if_empty(session, old_invoice)
    session.commit()
    session.expire_all()
    return to_out(get_line(session, line_id))


@router.delete("/transactions/{line_id}", status_code=204)
def delete_transaction(line_id: int, session: Session = Depends(get_session)):
    line = get_line(session, line_id)
    invoice_no = line.invoice_no
    session.delete(line)
    session.flush()
    delete_invoice_if_empty(session, invoice_no)
    session.commit()
    return Response(status_code=204)


@router.get("/daily", response_model=list[DailySummary])
def daily_summary(start: date, end: date, session: Session = Depends(get_session)):
    """Daily revenue series for a date range, aggregated in MySQL."""
    low, high = date_bounds(start, end)
    revenue = InvoiceLine.quantity * InvoiceLine.unit_price
    sale = Invoice.is_cancelled.is_(False)
    day = func.date(Invoice.invoice_date).label("date")
    stmt = (select(
                day,
                func.sum(case((sale, revenue), else_=0)).label("gross_revenue"),
                func.sum(revenue).label("net_revenue"),
                func.count(func.distinct(case((sale, Invoice.invoice_no)))).label("n_invoices"),
                func.sum(case((sale, InvoiceLine.quantity), else_=0)).label("total_quantity"),
                func.count().label("n_lines"))
            .join(InvoiceLine.invoice)
            .where(Invoice.invoice_date >= low, Invoice.invoice_date < high)
            .group_by(day).order_by(day))
    return [DailySummary(**row._mapping) for row in session.execute(stmt)]

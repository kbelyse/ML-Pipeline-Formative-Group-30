"""MongoDB connection and indexes.

Collection `transactions`: one document per invoice line, with the customer and
product embedded as sub-documents so a single read returns a complete record.
"""
from pymongo import ASCENDING, DESCENDING, MongoClient

from api.config import MONGO_DB, MONGO_URL

client = MongoClient(MONGO_URL)
db = client[MONGO_DB]
transactions = db["transactions"]


# Same validator as database/mongodb/collection_setup.js
VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["invoice_no", "invoice_date", "is_cancelled", "customer", "product",
                 "quantity", "unit_price", "revenue"],
    "properties": {
        "invoice_no": {"bsonType": "string"},
        "invoice_date": {"bsonType": "date"},
        "is_cancelled": {"bsonType": "bool"},
        "customer": {"bsonType": "object", "required": ["customer_id", "country"],
                     "properties": {"customer_id": {"bsonType": "string"},
                                    "country": {"bsonType": "string"}}},
        "product": {"bsonType": "object", "required": ["stock_code"],
                    "properties": {"stock_code": {"bsonType": "string"},
                                   "description": {"bsonType": ["string", "null"]}}},
        "quantity": {"bsonType": "int"},
        "unit_price": {"bsonType": "double", "minimum": 0, "exclusiveMinimum": True},
        "revenue": {"bsonType": "double"},
    },
}}


def init_mongo():
    if "transactions" in db.list_collection_names():
        db.command("collMod", "transactions", validator=VALIDATOR)
    else:
        db.create_collection("transactions", validator=VALIDATOR)
    # Date index supports the latest-record and date-range queries
    transactions.create_index([("invoice_date", DESCENDING)])
    transactions.create_index([("invoice_no", ASCENDING)])
    transactions.create_index([("customer.customer_id", ASCENDING)])

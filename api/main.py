"""FastAPI app exposing CRUD and time-series endpoints for MySQL and MongoDB.

Run with:  uvicorn api.main:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.mongo_db import init_mongo
from api.routers import mongo_transactions, sql_transactions
from api.sql_db import init_sql


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sql()
    init_mongo()
    yield


app = FastAPI(title="Online Retail Time-Series API",
              description="CRUD and time-series queries on Online Retail transactions "
                          "stored in MySQL and MongoDB.",
              version="1.0.0", lifespan=lifespan)

app.include_router(sql_transactions.router)
app.include_router(mongo_transactions.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "docs": "/docs"}

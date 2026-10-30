"""Load the cleaned transactions from Task 1 into MySQL and MongoDB.

Usage:
    python scripts/load_data.py                       # load everything into both databases
    python scripts/load_data.py --target sql --limit 50000
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import insert, text

sys.path.append(str(Path(__file__).resolve().parents[1]))
from api.mongo_db import init_mongo, transactions  # noqa: E402
from api.sql_db import Country, Customer, Invoice, InvoiceLine, Product, engine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data/processed/transactions_clean.csv.gz"
SCHEMA_SQL = ROOT / "database/sql/schema.sql"
CHUNK = 20_000


def read_clean_csv(path, limit=None):
    df = pd.read_csv(path, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str},
                     parse_dates=["InvoiceDate"], nrows=limit)
    df["CustomerID"] = df["CustomerID"].fillna("UNKNOWN")
    df["Description"] = df["Description"].where(df["Description"].notna(), None)
    return df


def records(frame):
    return frame.to_dict("records")


def run_schema(conn):
    """Recreate the tables and view from the Task 2 schema script."""
    lines = [l for l in SCHEMA_SQL.read_text().splitlines() if not l.strip().startswith("--")]
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            conn.execute(text(statement))


def load_sql(df):
    with engine.begin() as conn:
        run_schema(conn)

        countries = pd.DataFrame({"name": sorted(df["Country"].unique())})
        countries["country_id"] = range(1, len(countries) + 1)
        conn.execute(insert(Country), records(countries))
        country_ids = dict(zip(countries["name"], countries["country_id"]))

        conn.execute(insert(Customer),
                     [{"customer_id": c} for c in df["CustomerID"].unique()])

        # A stock code can have slightly different descriptions; keep the most frequent one
        products = (df.groupby("StockCode")["Description"]
                    .agg(lambda s: s.mode().iloc[0] if s.notna().any() else None).reset_index())
        products.columns = ["stock_code", "description"]
        conn.execute(insert(Product), records(products))

        # 43 invoices span two timestamps one minute apart; the first one is kept
        invoices = df.drop_duplicates("InvoiceNo")[["InvoiceNo", "InvoiceDate", "CustomerID",
                                                     "Country", "is_cancelled"]].copy()
        invoices["country_id"] = invoices.pop("Country").map(country_ids)
        invoices.columns = ["invoice_no", "invoice_date", "customer_id", "is_cancelled", "country_id"]
        for i in range(0, len(invoices), CHUNK):
            conn.execute(insert(Invoice), records(invoices.iloc[i:i + CHUNK]))

        lines = df[["InvoiceNo", "StockCode", "Quantity", "UnitPrice"]].copy()
        lines.columns = ["invoice_no", "stock_code", "quantity", "unit_price"]
        for i in range(0, len(lines), CHUNK):
            conn.execute(insert(InvoiceLine), records(lines.iloc[i:i + CHUNK]))
    print(f"MySQL: {len(countries)} countries, {df['CustomerID'].nunique()} customers, "
          f"{len(products)} products, {len(invoices)} invoices, {len(lines)} invoice lines")


def load_mongo(df):
    transactions.drop()
    init_mongo()
    docs = [{
        "invoice_no": r.InvoiceNo,
        "invoice_date": r.InvoiceDate.to_pydatetime(),
        "is_cancelled": bool(r.is_cancelled),
        "customer": {"customer_id": r.CustomerID, "country": r.Country},
        "product": {"stock_code": r.StockCode, "description": r.Description},
        "quantity": int(r.Quantity),
        "unit_price": float(r.UnitPrice),
        "revenue": round(float(r.Revenue), 3),
    } for r in df.itertuples(index=False)]
    for i in range(0, len(docs), CHUNK):
        transactions.insert_many(docs[i:i + CHUNK])
    print(f"MongoDB: {transactions.count_documents({})} transaction documents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--csv", default=DEFAULT_CSV, help="path to transactions_clean.csv(.gz)")
    parser.add_argument("--target", choices=["sql", "mongo", "both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="only load the first N rows")
    args = parser.parse_args()

    data = read_clean_csv(args.csv, args.limit)
    print(f"Read {len(data)} rows from {args.csv}")
    if args.target in ("sql", "both"):
        load_sql(data)
    if args.target in ("mongo", "both"):
        load_mongo(data)

# ML Pipeline Formative, Group 30: Online Retail Daily Revenue

Group assignment: forecasting daily net revenue for an online retailer, with the data stored in MySQL and MongoDB and served through an API.

**Dataset:** Online Retail (UCI Machine Learning Repository / Kaggle), about 540,000 transaction lines from 1 Dec 2010 to 9 Dec 2011.
**Target:** daily net revenue (sales minus cancellations).

## Repository structure

```
database/             Task 2: database design
  erd.png, erd.mmd    entity relationship diagram
  sql/schema.sql      MySQL tables, indexes and daily_revenue view
  sql/queries.sql     SQL queries
  mongodb/            collection setup, sample documents and queries
  query_results.md    output of all queries
  run_queries.sh      runs the queries and saves the output
api/                  Task 3: FastAPI app (CRUD and time-series endpoints)
  main.py             app entry point
  sql_db.py           MySQL tables (SQLAlchemy)
  mongo_db.py         MongoDB collection and indexes
  schemas.py          request and response models
  routers/            /sql and /mongo endpoints
scripts/
  load_data.py        builds the schema and loads the cleaned data into MySQL and MongoDB
tests/                API tests for both databases
data/processed/       cleaned dataset from Task 1
docker-compose.yml    local MySQL and MongoDB
```

## Setup

Requirements: Python 3.12 and Docker.

```bash
git clone https://github.com/kbelyse/ML-Pipeline-Formative-Group-30.git
cd ML-Pipeline-Formative-Group-30
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

docker compose up -d               # starts MySQL on 3306 and MongoDB on 27017
python scripts/load_data.py        # runs schema.sql, then loads data/processed/transactions_clean.csv.gz into both
./database/run_queries.sh          # optional: reruns the Task 2 queries
uvicorn api.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

## Task 2: Database design

### MySQL

![ERD](database/erd.png)

| Table | Purpose |
|---|---|
| `countries` | One row per country |
| `customers` | One row per customer; missing IDs are stored as `UNKNOWN` so foreign keys stay valid |
| `products` | One row per stock code with its description |
| `invoices` | One row per invoice: date, customer, country and whether it was cancelled |
| `invoice_lines` | One row per product line of an invoice: quantity and unit price |

`invoices.invoice_date` is indexed for the latest-record and date-range queries. The view `daily_revenue` turns the transactions into the daily series used for forecasting (gross revenue, net revenue, invoices and quantity per day), with the same definitions as the Task 1 notebook. Codes use a case-sensitive collation because the data contains codes such as `15056BL` and `15056bl` that are different products.

Script: [`database/sql/schema.sql`](database/sql/schema.sql)

### MongoDB

Collection `transactions` has one document per invoice line. The customer and product are embedded because they are small and always read with the line, so a single read returns a complete record without joins. A `$jsonSchema` validator enforces field types and a positive unit price, and `invoice_date` is indexed for time-series queries.

```json
{
  "invoice_no": "536365",
  "invoice_date": {"$date": "2010-12-01T08:26:00Z"},
  "is_cancelled": false,
  "customer": {"customer_id": "17850", "country": "United Kingdom"},
  "product": {"stock_code": "85123A", "description": "WHITE HANGING HEART T-LIGHT HOLDER"},
  "quantity": 6,
  "unit_price": 2.55,
  "revenue": 15.3
}
```

Setup script: [`database/mongodb/collection_setup.js`](database/mongodb/collection_setup.js). More examples, including a cancellation and an unknown customer: [`database/mongodb/sample_documents.json`](database/mongodb/sample_documents.json)

### Queries

| # | MySQL ([`queries.sql`](database/sql/queries.sql)) | MongoDB ([`queries.js`](database/mongodb/queries.js)) |
|---|---|---|
| 1 | Latest 5 transactions | Latest record |
| 2 | Daily revenue for 1 to 8 Dec 2011 | Records between 1 and 8 Dec 2011 |
| 3 | Monthly net revenue and average per trading day | Daily revenue for 1 to 8 Dec 2011 |
| 4 | Lag 1, lag 6 and 6-day moving average (window functions) | 6-day moving average (`$setWindowFields`) |
| 5 | Top 5 international markets | Top 5 products in Nov 2011 |

All results are in [`database/query_results.md`](database/query_results.md). Both databases return the same daily figures as the Task 1 notebook, for example 2010-12-01: gross revenue 57,442.33 and 127 invoices.

## Task 3: API endpoints

The same endpoints exist for both databases. Replace `{db}` with `sql` (MySQL) or `mongo` (MongoDB).

| Method | Endpoint | Description |
|---|---|---|
| POST | `/{db}/transactions` | Create a transaction line |
| GET | `/{db}/transactions?limit=100&offset=0` | List transactions (paginated) |
| GET | `/{db}/transactions/{id}` | Get one transaction |
| PUT | `/{db}/transactions/{id}` | Update a transaction (only the fields sent) |
| DELETE | `/{db}/transactions/{id}` | Delete a transaction |
| GET | `/{db}/transactions/latest` | Latest record by invoice date |
| GET | `/{db}/transactions/range?start=YYYY-MM-DD&end=YYYY-MM-DD` | Records in a date range (both dates inclusive) |
| GET | `/{db}/daily?start=YYYY-MM-DD&end=YYYY-MM-DD` | Daily revenue series aggregated by the database |

`{id}` is an integer for MySQL (`line_id`) and a MongoDB ObjectId string for MongoDB.

**Validation** follows the Task 1 cleaning rules: `unit_price` must be above 0, sales need a positive quantity, cancellations (invoice number starting with `C`) need a negative quantity, and a missing `customer_id` is stored as `UNKNOWN`. Invalid input returns `422`, a missing record `404`, and an invalid date range or MongoDB id `400`.

### Example requests

```bash
# Create
curl -X POST http://127.0.0.1:8000/sql/transactions \
  -H "Content-Type: application/json" \
  -d '{"invoice_no": "581590", "stock_code": "22613", "description": "PACK OF 20 SPACEBOY NAPKINS",
       "quantity": 12, "invoice_date": "2011-12-09T13:00:00", "unit_price": 0.85,
       "customer_id": "12680", "country": "France"}'

# Update and delete (use the id returned above)
curl -X PUT http://127.0.0.1:8000/sql/transactions/531209 -H "Content-Type: application/json" -d '{"quantity": 24}'
curl -X DELETE http://127.0.0.1:8000/sql/transactions/531209

# Time-series queries
curl http://127.0.0.1:8000/mongo/transactions/latest
curl "http://127.0.0.1:8000/mongo/transactions/range?start=2011-12-01&end=2011-12-08"
curl "http://127.0.0.1:8000/sql/daily?start=2011-12-01&end=2011-12-08"
```

Example response:

```json
{
  "id": 531208, "invoice_no": "581587", "stock_code": "22138",
  "description": "BAKING SET 9 PIECE RETROSPOT", "quantity": 3,
  "invoice_date": "2011-12-09T12:50:00", "unit_price": 4.95,
  "customer_id": "12680", "country": "France", "is_cancelled": false, "revenue": 14.85
}
```

### Tests

```bash
pytest
```

The tests run every endpoint against both databases, using separate `retail_test` databases so the loaded data is not changed.

### Check against Task 1

The `/daily` endpoint returns the same values as `aggregate_daily` in the Task 1 notebook, for example on 2010-12-01: gross revenue 57,442.33, 127 invoices, 26,808 units, from both MySQL and MongoDB.

## Team contributions

| Member | Task | Main components |
|---|---|---|
|  | Task 1: Preprocessing, EDA and model | |
| kbelyse | Task 2: SQL and MongoDB design | ERD, MySQL schema and view, MongoDB collection and validator, sample documents, queries and results |
| kbelyse | Task 3: API endpoints | FastAPI app, CRUD and time-series endpoints for MySQL and MongoDB, data loader, tests |
|  | Task 4: Prediction script | |

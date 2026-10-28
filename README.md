# ML Pipeline Formative, Group 30: Online Retail Daily Revenue

Group assignment: forecasting daily net revenue for an online retailer, with the data stored in MySQL and MongoDB and served through an API.

**Dataset:** Online Retail (UCI Machine Learning Repository / Kaggle), about 540,000 transaction lines from 1 Dec 2010 to 9 Dec 2011.
**Target:** daily net revenue (sales minus cancellations).

## Repository structure

```
api/                  Task 3: FastAPI app (CRUD and time-series endpoints)
  main.py             app entry point
  sql_db.py           MySQL tables (SQLAlchemy)
  mongo_db.py         MongoDB collection and indexes
  schemas.py          request and response models
  routers/            /sql and /mongo endpoints
scripts/
  load_data.py        loads the cleaned data into MySQL and MongoDB
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
python scripts/load_data.py        # loads data/processed/transactions_clean.csv.gz into both
uvicorn api.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

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
|  | Task 2: SQL and MongoDB design | |
| kbelyse | Task 3: API endpoints | FastAPI app, CRUD and time-series endpoints for MySQL and MongoDB, data loader, tests |
|  | Task 4: Prediction script | |

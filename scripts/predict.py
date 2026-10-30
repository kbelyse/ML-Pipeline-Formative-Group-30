"""Task 4: forecast the next trading day's net revenue.

Steps: fetch daily data from the API -> preprocess with the Task 1 feature
code (src/preprocessing.py) -> load the trained model -> predict.

Usage (API must be running):
    python scripts/predict.py
    python scripts/predict.py --db mongo --days 60
    python scripts/predict.py --source csv     # offline test, skips the API
"""
import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessing import FEATURES, aggregate_daily, make_features  # noqa: E402

CSV_PATH = ROOT / "data" / "processed" / "transactions_clean.csv.gz"
MODEL_PATH = ROOT / "models" / "best_model.pkl"
PLACEHOLDER_MODEL_PATH = ROOT / "models" / "placeholder_model.joblib"

API_URL = "http://127.0.0.1:8000"
HISTORY_DAYS = 60          # calendar days of history to pull from the API
MIN_HISTORY_ROWS = 25      # trading days needed: the 24-day rolling mean plus the day to predict
COMPLETE_AFTER_HOUR = 17   # a day whose last invoice is earlier than this is treated as unfinished

# Field names in the /daily response; the first one found is used.
FIELDS = {
    "date": ("date", "day"),
    "net_revenue": ("net_revenue",),
    "gross_revenue": ("gross_revenue",),
    "n_invoices": ("n_invoices", "invoices", "invoice_count"),
    "avg_basket": ("avg_basket",),
}


class PredictionError(Exception):
    """A problem the user can act on (API down, no model, not enough data)."""


def api_get(path: str, params: dict | None = None, base_url: str = API_URL):
    try:
        response = requests.get(f"{base_url}{path}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.ConnectionError:
        raise PredictionError(f"Cannot reach the API at {base_url}. Is uvicorn running?")
    except requests.Timeout:
        raise PredictionError(f"The API at {base_url} took too long to answer.")
    except requests.HTTPError as err:
        raise PredictionError(f"API error on {path}: {err}")
    except ValueError:
        raise PredictionError(f"The API returned something that is not JSON on {path}.")


def pick(record: dict, name: str, required: bool = True):
    for key in FIELDS[name]:
        if key in record:
            return record[key]
    if required:
        raise PredictionError(f"No field for '{name}' (tried {FIELDS[name]}). Fields present: {list(record)}")
    return None


def rows_to_daily(rows: list) -> pd.DataFrame:
    """Turn /daily records into the columns the Task 1 features need."""
    out = {}
    for r in rows:
        invoices = float(pick(r, "n_invoices"))
        basket = pick(r, "avg_basket", required=False)
        if basket is None:      # same formula as Task 1's aggregate_daily
            gross = float(pick(r, "gross_revenue"))
            basket = gross / invoices if invoices else 0.0
        out[pd.to_datetime(pick(r, "date")).normalize()] = {
            "net_revenue": float(pick(r, "net_revenue")),
            "n_invoices": invoices,
            "avg_basket": float(basket),
        }
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


def drop_unfinished_day(daily: pd.DataFrame, latest_ts: pd.Timestamp) -> pd.DataFrame:
    """Task 1 removed the last day because the data stops at midday; do the same here."""
    if latest_ts.hour < COMPLETE_AFTER_HOUR:
        return daily[daily.index < latest_ts.normalize()]
    return daily


def fetch_daily_from_api(db: str, days: int, base_url: str = API_URL) -> pd.DataFrame:
    latest = api_get(f"/{db}/transactions/latest", base_url=base_url)
    latest_ts = pd.to_datetime(latest["invoice_date"])
    start = latest_ts.normalize() - pd.Timedelta(days=days - 1)
    rows = api_get(
        f"/{db}/daily",
        params={"start": start.date().isoformat(), "end": latest_ts.date().isoformat()},
        base_url=base_url,
    )
    if isinstance(rows, dict):          # tolerate {"data": [...]} style wrappers
        rows = rows.get("data") or rows.get("items") or []
    if not rows:
        raise PredictionError(f"The API returned no daily data for {start.date()} to {latest_ts.date()}.")
    return drop_unfinished_day(rows_to_daily(rows), latest_ts)


def fetch_daily_from_csv(days: int) -> pd.DataFrame:
    """Offline stand-in for the API, for testing only."""
    df = pd.read_csv(CSV_PATH, dtype={"InvoiceNo": str, "StockCode": str}, parse_dates=["InvoiceDate"])
    daily = aggregate_daily(df)[["net_revenue", "n_invoices", "avg_basket"]]
    cutoff = daily.index.max() - pd.Timedelta(days=days - 1)
    return drop_unfinished_day(daily[daily.index >= cutoff], df["InvoiceDate"].max())


def load_model(path: Path | None = None):
    if path is None:
        path = MODEL_PATH if MODEL_PATH.exists() else PLACEHOLDER_MODEL_PATH
        if path == PLACEHOLDER_MODEL_PATH:
            print("WARNING: using the placeholder model, not the Task 1 model.", file=sys.stderr)
    if not path.exists():
        raise PredictionError(f"Model file not found: {path}")
    try:
        return joblib.load(path)
    except Exception as err:    # typically a scikit-learn version mismatch
        raise PredictionError(
            f"Could not load {path.name}: {err}. It was trained with scikit-learn 1.6.1; "
            "install that version (see requirements.txt)."
        )


def next_trading_date(last: pd.Timestamp) -> pd.Timestamp:
    """The shop never trades on Saturdays (Task 1, section 2.2). Holidays are not known."""
    nxt = last + pd.Timedelta(days=1)
    while nxt.day_of_week == 5:
        nxt += pd.Timedelta(days=1)
    return nxt


def build_input(daily: pd.DataFrame) -> pd.DataFrame:
    """Feature row for the next trading day, built with the Task 1 make_features.

    A zero-filled row stands in for the day to predict. make_features only uses
    earlier rows for that day's features, so the zeros never reach the model.
    """
    if len(daily) < MIN_HISTORY_ROWS:
        raise PredictionError(f"Need at least {MIN_HISTORY_ROWS} trading days of history, got {len(daily)}.")
    target = next_trading_date(daily.index[-1])
    stand_in = pd.DataFrame(0.0, index=[target], columns=daily.columns)
    features = make_features(pd.concat([daily, stand_in]))
    if target not in features.index:
        raise PredictionError("Could not build features for the next day; not enough clean history.")
    return features.loc[[target], FEATURES]


def forecast(daily: pd.DataFrame, model) -> tuple[pd.Timestamp, float]:
    X = build_input(daily)
    return X.index[0], float(model.predict(X)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--db", choices=["sql", "mongo"], default="sql", help="which database the API reads from")
    parser.add_argument("--days", type=int, default=HISTORY_DAYS, help="calendar days of history to fetch")
    parser.add_argument("--source", choices=["api", "csv"], default="api")
    parser.add_argument("--api-url", default=API_URL)
    parser.add_argument("--model", type=Path, default=None, help="path to a model file")
    args = parser.parse_args()

    try:
        print(f"1. Fetching last {args.days} days ({args.source}, {args.db})...")
        if args.source == "api":
            daily = fetch_daily_from_api(args.db, args.days, args.api_url)
        else:
            daily = fetch_daily_from_csv(args.days)
        print(f"   got {len(daily)} trading days: {daily.index.min().date()} to {daily.index.max().date()}")

        print("2. Loading model...")
        model = load_model(args.model)

        print("3. Preprocessing and predicting...")
        date, value = forecast(daily, model)
    except PredictionError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"\nForecast net revenue for {date.date()}: GBP {value:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

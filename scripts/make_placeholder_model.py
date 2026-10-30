"""Train a stand-in model so predict.py can be tested without the Task 1 model file.

NOT the real model. It repeats the Task 1 recipe (same features, Linear Regression
pipeline). Once models/best_model.pkl exists, predict.py uses that instead.
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessing import FEATURES, TARGET, aggregate_daily, make_features  # noqa: E402

CSV_PATH = ROOT / "data" / "processed" / "transactions_clean.csv.gz"
OUT_PATH = ROOT / "models" / "placeholder_model.joblib"


def main():
    df = pd.read_csv(CSV_PATH, dtype={"InvoiceNo": str, "StockCode": str}, parse_dates=["InvoiceDate"])
    daily = aggregate_daily(df)
    daily = daily[daily.index < "2011-12-09"]          # last day ends at midday (as in Task 1)
    data = make_features(daily)

    num_cols = [c for c in FEATURES if c != "dow"]
    model = make_pipeline(
        make_column_transformer((OneHotEncoder(handle_unknown="ignore"), ["dow"]),
                                (StandardScaler(), num_cols)),
        LinearRegression(),
    ).fit(data[FEATURES], data[TARGET])

    OUT_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, OUT_PATH)
    print(f"Saved placeholder model trained on {len(data)} days to {OUT_PATH}")


if __name__ == "__main__":
    main()

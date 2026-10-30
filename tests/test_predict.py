"""Tests for the Task 4 prediction script. The API is faked, so no server is needed."""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import predict
from src.preprocessing import FEATURES


class FakeModel:
    def predict(self, X):
        assert list(X.columns) == FEATURES
        return [123.0] * len(X)


def fake_api(path, params=None, base_url=None):
    if path.endswith("/transactions/latest"):
        return {"invoice_date": "2011-12-09T12:50:00"}     # midday: this day is unfinished
    days = [d for d in pd.date_range(params["start"], params["end"]) if d.dayofweek != 5]
    return [
        {"date": d.date().isoformat(), "net_revenue": 20000 + 100 * i,
         "gross_revenue": 21000 + 100 * i, "n_invoices": 50 + i}
        for i, d in enumerate(days)
    ]


@pytest.fixture
def daily():
    with patch.object(predict, "api_get", fake_api):
        return predict.fetch_daily_from_api("sql", 60)


def test_unfinished_last_day_is_dropped(daily):
    assert daily.index.max() == pd.Timestamp("2011-12-08")
    assert list(daily.columns) == ["net_revenue", "n_invoices", "avg_basket"]


def test_avg_basket_is_gross_over_invoices():
    row = predict.rows_to_daily([{"date": "2011-01-04", "net_revenue": 90.0, "gross_revenue": 100.0, "n_invoices": 4}])
    assert row["avg_basket"].iloc[0] == 25.0


def test_forecast_targets_next_trading_day(daily):
    date, value = predict.forecast(daily, FakeModel())
    assert date == pd.Timestamp("2011-12-09")
    assert value == 123.0


def test_next_trading_day_skips_saturday():
    assert predict.next_trading_date(pd.Timestamp("2011-12-09")) == pd.Timestamp("2011-12-11")   # Friday -> Sunday


def test_features_do_not_depend_on_the_day_being_predicted(daily):
    X = predict.build_input(daily)
    assert X["lag_1"].iloc[0] == daily["net_revenue"].iloc[-1]
    assert X["roll_mean_6"].iloc[0] == pytest.approx(daily["net_revenue"].iloc[-6:].mean())
    assert X["invoices_lag_1"].iloc[0] == daily["n_invoices"].iloc[-1]
    assert not X.isna().any(axis=None)


def test_too_little_history_is_rejected(daily):
    with pytest.raises(predict.PredictionError):
        predict.forecast(daily.tail(predict.MIN_HISTORY_ROWS - 1), FakeModel())


def test_unknown_response_fields_give_clear_error():
    with pytest.raises(predict.PredictionError):
        predict.rows_to_daily([{"foo": 1}])

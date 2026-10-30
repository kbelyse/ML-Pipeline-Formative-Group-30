"""Feature engineering for the daily revenue forecast.

One function builds the features for both training and prediction, so the
two can never drift apart. If the Task 1 notebook uses different lags,
moving averages or calendar features, change the constants below to match.
"""
import pandas as pd

LAGS = [1, 7, 14]          # revenue 1, 7 and 14 days before the day being predicted
MA_WINDOWS = [7, 14]       # moving average of the previous 7 and 14 days
FEATURES = (
    [f"lag_{k}" for k in LAGS]
    + [f"ma_{w}" for w in MA_WINDOWS]
    + ["day_of_week", "month"]
)
MIN_HISTORY_DAYS = max(max(LAGS), max(MA_WINDOWS)) + 1


def fill_missing_days(daily: pd.Series) -> pd.Series:
    """Put the series on a complete daily calendar; days with no sales become 0."""
    daily = daily.sort_index()
    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    return daily.reindex(full_index, fill_value=0.0)


def build_features(daily: pd.Series) -> pd.DataFrame:
    """Return one row per day with the features known the day before.

    Every feature is shifted so a row only uses information from earlier days
    (no leakage): the moving averages end the day before the row's date.
    """
    df = pd.DataFrame({"revenue": daily})
    for k in LAGS:
        df[f"lag_{k}"] = df["revenue"].shift(k)
    for w in MA_WINDOWS:
        df[f"ma_{w}"] = df["revenue"].shift(1).rolling(w).mean()
    df["day_of_week"] = df.index.dayofweek
    df["month"] = df.index.month
    return df


def next_day_features(daily: pd.Series) -> pd.DataFrame:
    """Features for the day after the last date in `daily` (a 1-row frame)."""
    daily = fill_missing_days(daily)
    next_date = daily.index[-1] + pd.Timedelta(days=1)
    extended = pd.concat([daily, pd.Series([float("nan")], index=[next_date])])
    return build_features(extended).loc[[next_date], FEATURES]

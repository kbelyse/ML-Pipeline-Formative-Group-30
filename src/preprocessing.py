"""Preprocessing pipeline for the Online Retail daily revenue forecast (Task 1).
Used by the prediction script (Task 4) to apply the same steps as model training."""
import pandas as pd

TARGET = "net_revenue"
NON_PRODUCT_CODES = ["POST", "DOT", "C2", "M", "D", "S", "B", "BANK CHARGES", "AMAZONFEE", "CRUK"]
FEATURES = ["lag_1", "lag_2", "lag_6", "lag_12", "roll_mean_6", "roll_mean_24",
            "roll_std_6", "invoices_lag_1", "basket_lag_1", "dow", "days_since_last"]


def clean_transactions(df):
    """Remove duplicates, non-products and invalid prices; flag cancellations; add Revenue."""
    df = df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df = df.drop_duplicates()
    df = df[~df["StockCode"].str.upper().isin(NON_PRODUCT_CODES)]
    df = df[~df["StockCode"].str.lower().str.startswith("gift_")]
    df = df[df["UnitPrice"] > 0]
    df["is_cancelled"] = df["InvoiceNo"].str.startswith("C")
    df = df[(df["Quantity"] > 0) | df["is_cancelled"]]
    df["CustomerID"] = df["CustomerID"].astype("string").fillna("UNKNOWN")
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]
    return df


def aggregate_daily(df):
    """Aggregate cleaned transactions into one row per trading day."""
    df = df.copy()
    df["date"] = df["InvoiceDate"].dt.normalize()
    sales = df[~df["is_cancelled"]]
    daily = sales.groupby("date").agg(
        gross_revenue=("Revenue", "sum"), n_invoices=("InvoiceNo", "nunique"),
        n_products=("StockCode", "nunique"), total_quantity=("Quantity", "sum"))
    known = sales[sales["CustomerID"] != "UNKNOWN"]
    daily["n_customers"] = known.groupby("date")["CustomerID"].nunique()
    daily["net_revenue"] = df.groupby("date")["Revenue"].sum()
    daily["cancel_rate"] = df.groupby("date")["is_cancelled"].mean()
    daily["avg_basket"] = daily["gross_revenue"] / daily["n_invoices"]
    uk = sales[sales["Country"] == "United Kingdom"].groupby("date")["Revenue"].sum()
    daily["uk_share"] = uk / daily["gross_revenue"]
    return daily.fillna(0)


def make_features(daily):
    """Create lag, rolling and calendar features using only past information."""
    f = daily.copy()
    rev = f[TARGET]
    for k in [1, 2, 6, 12]:
        f[f"lag_{k}"] = rev.shift(k)
    f["roll_mean_6"] = rev.shift(1).rolling(6).mean()
    f["roll_mean_24"] = rev.shift(1).rolling(24).mean()
    f["roll_std_6"] = rev.shift(1).rolling(6).std()
    f["invoices_lag_1"] = f["n_invoices"].shift(1)
    f["basket_lag_1"] = f["avg_basket"].shift(1)
    f["dow"] = f.index.dayofweek
    f["days_since_last"] = f.index.to_series().diff().dt.days
    return f.dropna()

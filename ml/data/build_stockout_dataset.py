
import os
import numpy as np
import pandas as pd

INPUT_PATH = "data/synthetic/daily_medicine_demand.csv"
OUTPUT_PATH = "ml/data/stockout_dataset.csv"

print("Loading synthetic demand data...")

df = pd.read_csv(
    INPUT_PATH,
    parse_dates=["date"]
)

df = df.sort_values(
    ["facility_id", "medicine_id", "date"]
).reset_index(drop=True)

# Validate required columns
required_columns = [
    "date",
    "facility_id",
    "medicine_id",
    "demand_quantity",
    "fulfilled_quantity",
    "unmet_demand",
    "stock_on_hand_end",
    "stockout_flag",
    "restock_quantity"
]

missing = [
    col for col in required_columns
    if col not in df.columns
]

if missing:
    raise ValueError(f"Missing columns: {missing}")

groups = df.groupby(
    ["facility_id", "medicine_id"],
    sort=False
)

# Historical demand features
for lag in [1, 7, 14, 30]:
    df[f"demand_lag_{lag}"] = groups[
        "demand_quantity"
    ].transform(lambda x: x.shift(lag))

for window in [7, 14, 30]:
    df[f"demand_rolling_mean_{window}"] = groups[
        "demand_quantity"
    ].transform(
        lambda x: x.shift(1).rolling(window).mean()
    )

# Historical inventory and stockout features
df["previous_stock"] = groups[
    "stock_on_hand_end"
].shift(1)

df["previous_unmet_demand"] = groups[
    "unmet_demand"
].shift(1)

df["previous_stockout"] = groups[
    "stockout_flag"
].shift(1)

df["previous_restock_quantity"] = groups[
    "restock_quantity"
].shift(1)

# Calendar features
df["day_of_week"] = df["date"].dt.dayofweek
df["month"] = df["date"].dt.month
df["is_weekend"] = (
    df["day_of_week"] >= 5
).astype(int)

# Future 7-day stockout target.
# Current day is excluded: prediction is made at the end
# of the current day for the following seven days.

def create_future_stockout_target(series):
    future_values = series.shift(-1)

    return (
        future_values
        .rolling(window=7, min_periods=7)
        .max()
        .shift(-6)
    )

df["stockout_risk"] = groups[
    "stockout_flag"
].transform(create_future_stockout_target)

# Remove rows without sufficient historical or future data
df = df.dropna().reset_index(drop=True)

df["stockout_risk"] = df[
    "stockout_risk"
].astype(int)

# Remove raw future outcome and identifiers that are not features
feature_columns = [
    "facility_id",
    "medicine_id",
    "demand_lag_1",
    "demand_lag_7",
    "demand_lag_14",
    "demand_lag_30",
    "demand_rolling_mean_7",
    "demand_rolling_mean_14",
    "demand_rolling_mean_30",
    "previous_stock",
    "previous_unmet_demand",
    "previous_stockout",
    "previous_restock_quantity",
    "day_of_week",
    "month",
    "is_weekend"
]

target_column = "stockout_risk"

output = df[
    ["date"] + feature_columns + [target_column]
].copy()

os.makedirs("ml/data", exist_ok=True)

output.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n========== STOCKOUT DATASET SUMMARY ==========")

print("Dataset shape:", output.shape)
print("\nTarget distribution:")
print(output[target_column].value_counts())

print("\nTarget percentages:")
print(
    output[target_column]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)

print("\nMissing values:", output.isnull().sum().sum())

print("\nSaved dataset:", OUTPUT_PATH)
print("\nStockout dataset generation completed!")

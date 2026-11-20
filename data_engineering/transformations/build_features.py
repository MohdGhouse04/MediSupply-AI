
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = Path(
    "data/synthetic/daily_medicine_demand.csv"
)

OUTPUT_FILE = Path(
    "data/processed/demand_features.csv"
)

GROUP_COLUMNS = [
    "facility_id",
    "medicine_id"
]

TARGET_COLUMNS = [
    "demand_quantity",
    "stockout_flag"
]


# --------------------------------------------------
# LOAD AND VALIDATE DATA
# --------------------------------------------------

def load_data():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input dataset not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "date",
        "facility_id",
        "medicine_id",
        "demand_quantity",
        "fulfilled_quantity",
        "unmet_demand",
        "stockout_flag",
        "stock_on_hand_end"
    ]

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(
        GROUP_COLUMNS + ["date"]
    ).reset_index(drop=True)

    duplicate_count = df.duplicated(
        subset=GROUP_COLUMNS + ["date"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate daily records."
        )

    return df


# --------------------------------------------------
# CREATE LAG FEATURES
# --------------------------------------------------

def create_lag_features(df):

    grouped = df.groupby(
        GROUP_COLUMNS,
        sort=False
    )

    # Previous demand.
    for lag in [1, 7, 14, 30]:

        df[f"demand_lag_{lag}"] = (
            grouped["demand_quantity"].shift(lag)
        )

    # Previous day's stock information.
    df["previous_stock"] = (
        grouped["stock_on_hand_end"].shift(1)
    )

    # Previous stockout information.
    df["previous_stockout"] = (
        grouped["stockout_flag"].shift(1)
    )

    df["previous_unmet_demand"] = (
        grouped["unmet_demand"].shift(1)
    )

    return df


# --------------------------------------------------
# CREATE ROLLING FEATURES
# --------------------------------------------------

def create_rolling_features(df):

    grouped = df.groupby(
        GROUP_COLUMNS,
        sort=False
    )

    # Shift by one day before calculating averages.
    # This prevents current-day demand from leaking
    # into the prediction features.

    for window in [7, 14, 30]:

        df[f"demand_rolling_mean_{window}"] = (
            grouped["demand_quantity"]
            .transform(
                lambda series:
                series.shift(1)
                .rolling(window=window)
                .mean()
            )
        )

    return df


# --------------------------------------------------
# CREATE CALENDAR FEATURES
# --------------------------------------------------

def create_calendar_features(df):

    df["day_of_week"] = df["date"].dt.dayofweek

    df["month"] = df["date"].dt.month

    df["day_of_year"] = df["date"].dt.dayofyear

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    # Cyclical encoding for annual seasonality.

    df["month_sin"] = np.sin(
        2 * np.pi * df["month"] / 12
    )

    df["month_cos"] = np.cos(
        2 * np.pi * df["month"] / 12
    )

    df["day_of_year_sin"] = np.sin(
        2 * np.pi * df["day_of_year"] / 365.25
    )

    df["day_of_year_cos"] = np.cos(
        2 * np.pi * df["day_of_year"] / 365.25
    )

    return df


# --------------------------------------------------
# BUILD FINAL FEATURE DATASET
# --------------------------------------------------

def build_features():

    print("Loading historical demand data...")

    df = load_data()

    print("Creating lag features...")

    df = create_lag_features(df)

    print("Creating rolling features...")

    df = create_rolling_features(df)

    print("Creating calendar features...")

    df = create_calendar_features(df)

    # Remove records without sufficient history.
    # The 30-day lag requires at least 30 previous days.

    feature_columns = [
        "demand_lag_1",
        "demand_lag_7",
        "demand_lag_14",
        "demand_lag_30",
        "previous_stock",
        "previous_stockout",
        "previous_unmet_demand",
        "demand_rolling_mean_7",
        "demand_rolling_mean_14",
        "demand_rolling_mean_30"
    ]

    df = df.dropna(
        subset=feature_columns
    ).copy()

    # Validate final dataset.

    if df[feature_columns].isnull().any().any():
        raise ValueError(
            "Missing values found in feature columns."
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nFeature engineering completed!")

    print("Total records:", len(df))

    print(
        "Number of features:",
        len(feature_columns) + 7
    )

    print(
        "Missing values:",
        df.isnull().sum().sum()
    )

    print(
        "Output file:",
        OUTPUT_FILE
    )

    print("\nFeature columns:")

    print(feature_columns)

    print("\nTarget columns:")

    print(TARGET_COLUMNS)

    print("\nMedicine-wise records:")

    print(
        df.groupby("generic_name").size()
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    build_features()

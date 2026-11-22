import os
import pandas as pd

INPUT_PATH = "data/synthetic/daily_medicine_demand.csv"
OUTPUT_PATH = "ml/data/live_stockout_features.csv"

FEATURES = [
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


def main():

    print("Loading raw demand data...")

    df = pd.read_csv(
        INPUT_PATH,
        parse_dates=["date"]
    )

    df = df.sort_values(
        ["facility_id", "medicine_id", "date"]
    ).reset_index(drop=True)

    groups = df.groupby(
        ["facility_id", "medicine_id"],
        sort=False
    )

    # Demand history features
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

    # Previous inventory and operational information
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

    # Select the latest completed observation per combination
    latest = (
        df.dropna(subset=FEATURES)
        .groupby(
            ["facility_id", "medicine_id"],
            as_index=False,
            sort=False
        )
        .tail(1)
        .copy()
    )

    latest = latest.sort_values(
        ["facility_id", "medicine_id"]
    ).reset_index(drop=True)

    output = latest[["date"] + FEATURES].copy()

    os.makedirs("ml/data", exist_ok=True)

    output.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("\n========== LIVE STOCKOUT FEATURES ==========")
    print("Feature records:", len(output))
    print("Latest observation:", output["date"].max().date())
    print("Missing values:", output[FEATURES].isnull().sum().sum())

    print("\nLatest feature records:")
    print(
        output[
            ["facility_id", "medicine_id", "date", "previous_stock"]
        ].to_string(index=False)
    )

    print("\nSaved:", OUTPUT_PATH)
    print("Live feature generation completed!")


if __name__ == "__main__":
    main()

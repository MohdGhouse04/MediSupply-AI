
import os
import joblib
import numpy as np
import pandas as pd

MODEL_PATH = "ml/models/saved/gradient_boosting_demand.joblib"
DATA_PATH = "data/synthetic/daily_medicine_demand.csv"
OUTPUT_PATH = "data/processed/multi_horizon_forecasts.csv"

FEATURES = [
    "facility_id",
    "medicine_id",
    "demand_lag_1",
    "demand_lag_7",
    "demand_lag_14",
    "demand_lag_30",
    "previous_stock",
    "previous_stockout",
    "previous_unmet_demand",
    "demand_rolling_mean_7",
    "demand_rolling_mean_14",
    "demand_rolling_mean_30",
    "day_of_week",
    "month",
    "day_of_year",
    "is_weekend",
    "month_sin",
    "month_cos",
    "day_of_year_sin",
    "day_of_year_cos"
]


def make_features(history, facility_id, medicine_id, date):

    demand = history["demand_quantity"].tolist()

    def lag(n):
        return demand[-n] if len(demand) >= n else np.mean(demand)

    def rolling(n):
        return np.mean(demand[-n:])

    day_of_year = date.dayofyear
    month = date.month

    return {
        "facility_id": facility_id,
        "medicine_id": medicine_id,
        "demand_lag_1": lag(1),
        "demand_lag_7": lag(7),
        "demand_lag_14": lag(14),
        "demand_lag_30": lag(30),
        "previous_stock": history["stock_on_hand_end"].iloc[-1],
        "previous_stockout": history["stockout"].iloc[-1],
        "previous_unmet_demand": history["unmet_demand"].iloc[-1],
        "demand_rolling_mean_7": rolling(7),
        "demand_rolling_mean_14": rolling(14),
        "demand_rolling_mean_30": rolling(30),
        "day_of_week": date.day_of_week,
        "month": month,
        "day_of_year": day_of_year,
        "is_weekend": int(date.day_of_week >= 5),
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        "day_of_year_sin": np.sin(2 * np.pi * day_of_year / 365),
        "day_of_year_cos": np.cos(2 * np.pi * day_of_year / 365)
    }


def forecast_group(model, group, horizon):

    group = group.sort_values("date").copy()

    history = group[
    [
        "demand_quantity",
        "stock_on_hand_end",
        "stockout_flag",
        "unmet_demand"
    ]
    ].copy().reset_index(drop=True)

    history = history.rename(
    columns={"stockout_flag": "stockout"}
    )
    facility_id = int(group["facility_id"].iloc[0])
    medicine_id = int(group["medicine_id"].iloc[0])

    last_date = group["date"].max()
    forecasts = []

    for step in range(1, horizon + 1):

        forecast_date = last_date + pd.Timedelta(days=step)

        feature_row = make_features(
            history,
            facility_id,
            medicine_id,
            forecast_date
        )

        X = pd.DataFrame([feature_row])[FEATURES]

        predicted_demand = max(
            0,
            float(model.predict(X)[0])
        )

        forecasts.append({
            "date": forecast_date,
            "facility_id": facility_id,
            "medicine_id": medicine_id,
            "forecast_day": step,
            "predicted_demand": round(predicted_demand, 2)
        })

        # Do not assume future inventory receipts or stockouts.
        # This is a demand forecast, not a future stock simulation.
        new_row = pd.DataFrame([{
            "demand_quantity": predicted_demand,
            "stock_on_hand_end": history["stock_on_hand_end"].iloc[-1],
            "stockout": 0,
            "unmet_demand": 0
        }])

        history = pd.concat(
            [history, new_row],
            ignore_index=True
        )

    return forecasts


def main():

    print("Loading model and historical data...")

    model = joblib.load(MODEL_PATH)

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["date"]
    )

    all_forecasts = []

    for (facility_id, medicine_id), group in df.groupby(
        ["facility_id", "medicine_id"]
    ):

        print(
            f"Forecasting facility {facility_id}, "
            f"medicine {medicine_id}"
        )

        for horizon in [7, 14, 30, 60]:

            forecasts = forecast_group(
                model,
                group,
                horizon
            )

            for row in forecasts:
                row["horizon"] = horizon

            all_forecasts.extend(forecasts)

    result = pd.DataFrame(all_forecasts)

    os.makedirs("data/processed", exist_ok=True)

    result.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("\n========== FORECAST SUMMARY ==========")

    summary = (
        result.groupby(
            ["facility_id", "medicine_id", "horizon"]
        )["predicted_demand"]
        .sum()
        .reset_index()
    )

    print(summary.to_string(index=False))

    print("\nSaved forecasts to:", OUTPUT_PATH)
    print("Total forecast records:", len(result))
    print("Multi-horizon forecasting completed!")


if __name__ == "__main__":
    main()

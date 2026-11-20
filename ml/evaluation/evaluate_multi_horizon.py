
import joblib
import numpy as np
import pandas as pd

from ml.models.multi_horizon_forecasting import forecast_group

MODEL_PATH = "ml/models/saved/gradient_boosting_demand.joblib"
RAW_PATH = "data/synthetic/daily_medicine_demand.csv"
FEATURE_PATH = "data/processed/demand_features.csv"

print("Loading model and datasets...")

model = joblib.load(MODEL_PATH)

raw = pd.read_csv(RAW_PATH, parse_dates=["date"])
features = pd.read_csv(FEATURE_PATH, parse_dates=["date"])

# Reproduce the chronological training split.
dates = sorted(features["date"].unique())
split_index = int(len(dates) * 0.8)
cutoff_date = dates[split_index - 1]

print("Training cutoff:", cutoff_date)

all_results = []

for (facility_id, medicine_id), group in raw.groupby(
    ["facility_id", "medicine_id"]
):

    history = group[group["date"] <= cutoff_date].copy()
    actual = group[group["date"] > cutoff_date].copy()

    # Forecast 30 days using only information available
    # up to the training cutoff.
    predictions = forecast_group(
        model,
        history,
        30
    )

    predictions = pd.DataFrame(predictions)

    comparison = predictions.merge(
        actual[["date", "facility_id", "medicine_id",
                "demand_quantity"]],
        on=["date", "facility_id", "medicine_id"],
        how="inner"
    )

    all_results.append(comparison)

results = pd.concat(all_results, ignore_index=True)

print("\n========== MULTI-HORIZON BACKTEST ==========")

for horizon in [7, 14, 30]:

    subset = results[
        results["forecast_day"] <= horizon
    ]

    actual_values = subset["demand_quantity"].to_numpy()
    predicted_values = subset["predicted_demand"].to_numpy()

    mae = np.mean(np.abs(actual_values - predicted_values))

    rmse = np.sqrt(
        np.mean((actual_values - predicted_values) ** 2)
    )

    wape = (
        np.sum(np.abs(actual_values - predicted_values))
        / np.sum(np.abs(actual_values))
    ) * 100

    print(f"\n{horizon}-DAY FORECAST")
    print("Records:", len(subset))
    print("MAE:", round(mae, 3))
    print("RMSE:", round(rmse, 3))
    print("WAPE:", round(wape, 2), "%")

results.to_csv(
    "data/processed/multi_horizon_backtest.csv",
    index=False
)

print("\nBacktest saved successfully!")

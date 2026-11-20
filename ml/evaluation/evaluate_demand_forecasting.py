
import numpy as np
import pandas as pd

PATH = "data/processed/forecast_test_predictions.csv"

df = pd.read_csv(PATH)

def evaluate(group):
    actual = group["demand_quantity"].to_numpy()
    predicted = group["predicted_demand"].to_numpy()

    error = predicted - actual

    return pd.Series({
        "Records": len(group),
        "MAE": np.mean(np.abs(error)),
        "RMSE": np.sqrt(np.mean(error ** 2)),
        "WAPE (%)": (
            np.sum(np.abs(error)) / np.sum(np.abs(actual)) * 100
        ),
        "Bias": np.mean(error)
    })

print("\n========== MEDICINE-WISE EVALUATION ==========")

medicine_results = (
    df.groupby("medicine_id")
    .apply(evaluate, include_groups=False)
)

print(medicine_results.round(3).to_string())

print("\n========== FACILITY-WISE EVALUATION ==========")

facility_results = (
    df.groupby("facility_id")
    .apply(evaluate, include_groups=False)
)

print(facility_results.round(3).to_string())

print("\n========== OVERALL EVALUATION ==========")

print(evaluate(df).round(3))

print("\n========== PREDICTION SAMPLE ==========")

print(df.head(10).to_string(index=False))

print("\nEvaluation completed successfully!")

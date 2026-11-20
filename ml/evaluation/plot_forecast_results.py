
import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv(
    "data/processed/forecast_test_predictions.csv",
    parse_dates=["date"]
)

os.makedirs("data/processed/forecast_charts", exist_ok=True)

# Overall actual vs predicted demand
daily = (
    df.groupby("date")
    [["demand_quantity", "predicted_demand"]]
    .sum()
)

plt.figure(figsize=(14, 6))

plt.plot(
    daily.index,
    daily["demand_quantity"],
    label="Actual Demand"
)

plt.plot(
    daily.index,
    daily["predicted_demand"],
    label="Predicted Demand"
)

plt.title("Actual vs Predicted Daily Medicine Demand")
plt.xlabel("Date")
plt.ylabel("Demand Quantity")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()

plt.savefig(
    "data/processed/forecast_charts/actual_vs_predicted.png"
)

plt.close()

# Prediction error distribution
df["prediction_error"] = (
    df["predicted_demand"] - df["demand_quantity"]
)

plt.figure(figsize=(10, 5))

plt.hist(
    df["prediction_error"],
    bins=30,
    edgecolor="black"
)

plt.title("Demand Forecast Prediction Error Distribution")
plt.xlabel("Prediction Error")
plt.ylabel("Frequency")
plt.grid(alpha=0.3)
plt.tight_layout()

plt.savefig(
    "data/processed/forecast_charts/error_distribution.png"
)

plt.close()

print("Forecast charts generated successfully!")

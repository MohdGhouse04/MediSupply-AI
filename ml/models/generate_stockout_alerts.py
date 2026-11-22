from pathlib import Path

import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = ROOT / "ml/data/live_stockout_features.csv"
MODEL_PATH = ROOT / "ml/models/saved/best_stockout_model.joblib"
THRESHOLD_PATH = ROOT / "ml/models/saved/stockout_threshold.joblib"

OUTPUT_PATH = ROOT / "ml/data/stockout_alerts.csv"


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
    "is_weekend",
]


def load_threshold(path):

    artifact = joblib.load(path)

    if isinstance(artifact, (int, float)):
        return float(artifact)

    if isinstance(artifact, dict):
        for key in [
            "threshold",
            "selected_threshold",
            "best_threshold"
        ]:
            if key in artifact:
                return float(artifact[key])

    raise ValueError(
        f"Unable to identify threshold in {path}"
    )


def main():

    print("Loading stockout model...")

    model = joblib.load(MODEL_PATH)
    threshold = load_threshold(THRESHOLD_PATH)

    print(f"Selected threshold: {threshold:.4f}")

    print("\nLoading live stockout features...")

    latest = pd.read_csv(
        DATA_PATH,
        parse_dates=["date"]
    )

    missing = [
        column for column in FEATURES
        if column not in latest.columns
    ]

    if missing:
        raise ValueError(
            f"Missing model features: {missing}"
        )

    if latest.empty:
        raise ValueError("Live feature dataset is empty.")

    if latest[FEATURES].isnull().any().any():
        raise ValueError("Live features contain missing values.")

    print("Feature records:", len(latest))
    print("Latest observation:", latest["date"].max().date())

    X = latest[FEATURES]

    print("\nPredicting stockout probabilities...")

    probabilities = model.predict_proba(X)[:, 1]

    latest["stockout_probability"] = probabilities
    latest["risk_threshold"] = threshold

    latest["risk_status"] = (
        latest["stockout_probability"] >= threshold
    ).map({
        True: "HIGH_RISK",
        False: "LOW_RISK"
    })

    latest["alert_action"] = latest["risk_status"].map({
        "HIGH_RISK": "REVIEW_INVENTORY",
        "LOW_RISK": "NO_IMMEDIATE_ALERT"
    })

    output_columns = [
        "date",
        "facility_id",
        "medicine_id",
        "stockout_probability",
        "risk_threshold",
        "risk_status",
        "alert_action",
        "previous_stock",
        "previous_unmet_demand",
        "demand_rolling_mean_7",
        "demand_rolling_mean_14",
        "demand_rolling_mean_30"
    ]

    alerts = latest[output_columns].copy()

    alerts["stockout_probability"] = (
        alerts["stockout_probability"].round(4)
    )

    alerts["risk_threshold"] = (
        alerts["risk_threshold"].round(4)
    )

    alerts.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("\n========== STOCKOUT ALERT SUMMARY ==========")

    print(alerts["risk_status"].value_counts())

    print("\n========== GENERATED ALERTS ==========")

    print(
        alerts[
            [
                "facility_id",
                "medicine_id",
                "stockout_probability",
                "risk_status",
                "alert_action"
            ]
        ].to_string(index=False)
    )

    print(f"\nSaved alerts to: {OUTPUT_PATH}")
    print("\nStockout alert generation completed!")


if __name__ == "__main__":
    main()

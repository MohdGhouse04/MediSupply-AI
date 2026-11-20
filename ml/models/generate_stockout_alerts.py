
from pathlib import Path

import joblib
import pandas as pd


# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = ROOT / "ml/data/stockout_dataset.csv"
MODEL_PATH = ROOT / "ml/models/saved/best_stockout_model.joblib"
THRESHOLD_PATH = ROOT / "ml/models/saved/stockout_threshold.joblib"

OUTPUT_PATH = ROOT / "ml/data/stockout_alerts.csv"


# --------------------------------------------------
# MODEL FEATURES
# Must match the training feature order
# --------------------------------------------------

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


# --------------------------------------------------
# LOAD THRESHOLD
# --------------------------------------------------

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
        f"Unable to identify threshold in {path}. "
        f"Artifact type: {type(artifact)}"
    )


# --------------------------------------------------
# GENERATE ALERTS
# --------------------------------------------------

def main():

    print("Loading stockout model...")

    model = joblib.load(MODEL_PATH)
    threshold = load_threshold(THRESHOLD_PATH)

    print(f"Selected threshold: {threshold:.4f}")

    print("\nLoading stockout dataset...")

    df = pd.read_csv(DATA_PATH)

    df["date"] = pd.to_datetime(df["date"])

    missing = [
        column for column in FEATURES
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing model features: {missing}"
        )

    # Latest eligible historical observation
    latest = (
        df.sort_values("date")
        .groupby(
            ["facility_id", "medicine_id"],
            as_index=False
        )
        .tail(1)
        .copy()
    )

    latest = latest.sort_values(
        ["facility_id", "medicine_id"]
    )

    print(f"Facility-medicine combinations: {len(latest)}")
    print(f"Latest eligible date: {latest['date'].max().date()}")

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

    # --------------------------------------------------
    # OUTPUT
    # --------------------------------------------------

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

    alerts.to_csv(OUTPUT_PATH, index=False)

    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------

    print("\n========== STOCKOUT ALERT SUMMARY ==========")

    print(
        alerts["risk_status"].value_counts()
    )

    print("\n========== GENERATED ALERTS ==========")

    high_risk = alerts[
        alerts["risk_status"] == "HIGH_RISK"
    ]

    if high_risk.empty:
        print("No high-risk alerts generated.")

    else:
        print(
            high_risk[
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

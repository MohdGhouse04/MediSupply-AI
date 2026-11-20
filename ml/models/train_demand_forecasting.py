
import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor
)
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATA_PATH = "data/processed/demand_features.csv"
MODEL_DIR = "ml/models/saved"
OUTPUT_DIR = "data/processed"

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

TARGET = "demand_quantity"


def calculate_metrics(actual, predicted):
    predicted = np.maximum(predicted, 0)

    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    wape = (
        np.sum(np.abs(actual - predicted))
        / np.sum(np.abs(actual))
    ) * 100

    return {
        "MAE": round(mae, 3),
        "RMSE": round(rmse, 3),
        "WAPE": round(wape, 2)
    }


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading demand dataset...")

    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    missing_columns = [
        col for col in FEATURES + [TARGET]
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    split_index = int(df["date"].nunique() * 0.8)
    dates = sorted(df["date"].unique())

    train_dates = dates[:split_index]
    test_dates = dates[split_index:]

    train_df = df[df["date"].isin(train_dates)]
    test_df = df[df["date"].isin(test_dates)]

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET]

    X_test = test_df[FEATURES]
    y_test = test_df[TARGET]

    print("Training rows:", len(X_train))
    print("Testing rows:", len(X_test))

    results = []

    # Baseline model
    baseline_predictions = test_df["demand_lag_7"].to_numpy()

    baseline_metrics = calculate_metrics(
        y_test.to_numpy(),
        baseline_predictions
    )

    results.append({
        "Model": "Lag-7 Baseline",
        **baseline_metrics
    })

    # Random Forest
    print("\nTraining Random Forest...")

    rf_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=15,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    rf_model.fit(X_train, y_train)

    rf_predictions = rf_model.predict(X_test)

    rf_metrics = calculate_metrics(
        y_test.to_numpy(),
        rf_predictions
    )

    results.append({
        "Model": "Random Forest",
        **rf_metrics
    })

    joblib.dump(
        rf_model,
        f"{MODEL_DIR}/random_forest_demand.joblib"
    )

    # Gradient Boosting
    print("\nTraining HistGradientBoosting...")

    gb_model = HistGradientBoostingRegressor(
        max_iter=200,
        learning_rate=0.05,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=42
    )

    gb_model.fit(X_train, y_train)

    gb_predictions = gb_model.predict(X_test)

    gb_metrics = calculate_metrics(
        y_test.to_numpy(),
        gb_predictions
    )

    results.append({
        "Model": "HistGradientBoosting",
        **gb_metrics
    })

    joblib.dump(
        gb_model,
        f"{MODEL_DIR}/gradient_boosting_demand.joblib"
    )

    # Model comparison
    results_df = pd.DataFrame(results)

    results_df.to_csv(
        f"{OUTPUT_DIR}/forecast_model_metrics.csv",
        index=False
    )

    print("\n========== MODEL COMPARISON ==========")
    print(results_df.to_string(index=False))

    # Save test predictions from the best model
    model_predictions = {
        "Random Forest": rf_predictions,
        "HistGradientBoosting": gb_predictions
    }

    best_model_name = min(
        [r for r in results if r["Model"] != "Lag-7 Baseline"],
        key=lambda x: x["WAPE"]
    )["Model"]

    best_predictions = np.maximum(
        model_predictions[best_model_name],
        0
    )

    predictions_df = test_df[
        ["date", "facility_id", "medicine_id", TARGET]
    ].copy()

    predictions_df["predicted_demand"] = best_predictions
    predictions_df["best_model"] = best_model_name

    predictions_df.to_csv(
        f"{OUTPUT_DIR}/forecast_test_predictions.csv",
        index=False
    )

    # Feature importance
    importance_df = pd.DataFrame({
        "feature": FEATURES,
        "importance": rf_model.feature_importances_
    }).sort_values(
        "importance",
        ascending=False
    )

    importance_df.to_csv(
        f"{OUTPUT_DIR}/feature_importance.csv",
        index=False
    )

    print("\n========== TOP FEATURES ==========")
    print(importance_df.head(10).to_string(index=False))

    print("\nBest model:", best_model_name)
    print("\nTraining completed successfully!")


if __name__ == "__main__":
    main()

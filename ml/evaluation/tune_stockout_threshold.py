
import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    confusion_matrix
)

DATA_PATH = "ml/data/stockout_dataset.csv"
MODEL_DIR = "ml/models/saved"
OUTPUT_DIR = "ml/data"

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


def metrics(y, probabilities, threshold):

    predictions = (
        probabilities >= threshold
    ).astype(int)

    return {
        "precision": precision_score(
            y, predictions, zero_division=0
        ),
        "recall": recall_score(
            y, predictions, zero_division=0
        ),
        "f1": f1_score(
            y, predictions, zero_division=0
        )
    }


def main():

    os.makedirs(MODEL_DIR, exist_ok=True)

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["date"]
    ).sort_values("date").reset_index(drop=True)

    dates = sorted(df["date"].unique())

    train_boundary = pd.Timestamp(
        dates[int(len(dates) * 0.70)]
    )

    test_boundary = pd.Timestamp(
        dates[int(len(dates) * 0.85)]
    )

    # Seven-day purging prevents overlapping
    # future-label windows across partitions.
    train_df = df[
        df["date"] < train_boundary - pd.Timedelta(days=7)
    ]

    val_df = df[
        (df["date"] >= train_boundary) &
        (df["date"] < test_boundary - pd.Timedelta(days=7))
    ]

    test_df = df[
        df["date"] >= test_boundary
    ]

    X_train = train_df[FEATURES]
    y_train = train_df["stockout_risk"]

    X_val = val_df[FEATURES]
    y_val = val_df["stockout_risk"]

    X_test = test_df[FEATURES]
    y_test = test_df["stockout_risk"]

    print("Training records:", len(train_df))
    print("Validation records:", len(val_df))
    print("Testing records:", len(test_df))

    if min(y_train.sum(), y_val.sum(), y_test.sum()) == 0:
        raise ValueError(
            "At least one partition has no positive stockout cases."
        )

    models = {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(
                class_weight="balanced",
                max_iter=2000,
                random_state=42
            ))
        ]),

        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1
        )
    }

    trained_models = {}
    validation_scores = {}

    print("\n========== VALIDATION MODEL COMPARISON ==========")

    for name, model in models.items():

        model.fit(X_train, y_train)

        probabilities = model.predict_proba(X_val)[:, 1]

        trained_models[name] = model
        validation_scores[name] = probabilities

        pr_auc = average_precision_score(
            y_val, probabilities
        )

        print(name, "| Validation PR-AUC:", round(pr_auc, 4))

    # Select model using validation PR-AUC.
    best_name = max(
        validation_scores,
        key=lambda name: average_precision_score(
            y_val, validation_scores[name]
        )
    )

    best_model = trained_models[best_name]
    val_probabilities = validation_scores[best_name]

    # Choose the highest F1 threshold among thresholds
    # that achieve at least 80% validation recall.
    candidates = []

    for threshold in np.arange(0.05, 0.96, 0.01):

        result = metrics(
            y_val,
            val_probabilities,
            threshold
        )

        if result["recall"] >= 0.80:
            candidates.append({
                "threshold": threshold,
                **result
            })

    if not candidates:
        raise ValueError(
            "No threshold achieved 80% validation recall. "
            "Review model performance and threshold range."
        )

    selected = max(
        candidates,
        key=lambda item: item["f1"]
    )

    threshold = selected["threshold"]

    # Evaluate exactly once on the untouched test set.
    test_probabilities = best_model.predict_proba(
        X_test
    )[:, 1]

    test_metrics = metrics(
        y_test,
        test_probabilities,
        threshold
    )

    print("\n========== SELECTED MODEL ==========")
    print("Model:", best_name)
    print("Selected threshold:", round(threshold, 2))

    print("\nValidation metrics:")
    print({
        key: round(value, 4)
        for key, value in selected.items()
        if key != "threshold"
    })

    print("\n========== FINAL TEST RESULTS ==========")
    print({
        key: round(value, 4)
        for key, value in test_metrics.items()
    })

    print(
        "Test PR-AUC:",
        round(
            average_precision_score(
                y_test, test_probabilities
            ), 4
        )
    )

    predictions = (
        test_probabilities >= threshold
    ).astype(int)

    print("\nConfusion matrix:")
    print(confusion_matrix(y_test, predictions))

    joblib.dump(
        best_model,
        f"{MODEL_DIR}/best_stockout_model.joblib"
    )

    joblib.dump(
        threshold,
        f"{MODEL_DIR}/stockout_threshold.joblib"
    )

    output = test_df[
        ["date", "facility_id", "medicine_id", "stockout_risk"]
    ].copy()

    output["stockout_probability"] = test_probabilities
    output["predicted_stockout"] = predictions

    output.to_csv(
        f"{OUTPUT_DIR}/stockout_threshold_test_results.csv",
        index=False
    )

    print("\nSaved selected model and threshold.")
    print("Threshold evaluation completed!")


if __name__ == "__main__":
    main()

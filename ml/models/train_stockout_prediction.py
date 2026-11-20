
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
    roc_auc_score,
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

TARGET = "stockout_risk"


def evaluate_model(y_true, probabilities, threshold=0.5):

    predictions = (
        probabilities >= threshold
    ).astype(int)

    return {
        "Precision": precision_score(
            y_true, predictions, zero_division=0
        ),
        "Recall": recall_score(
            y_true, predictions, zero_division=0
        ),
        "F1": f1_score(
            y_true, predictions, zero_division=0
        ),
        "PR_AUC": average_precision_score(
            y_true, probabilities
        ),
        "ROC_AUC": roc_auc_score(
            y_true, probabilities
        )
    }


def main():

    os.makedirs(MODEL_DIR, exist_ok=True)

    print("Loading stockout dataset...")

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["date"]
    )

    df = df.sort_values("date").reset_index(drop=True)

    dates = sorted(df["date"].unique())

    split_index = int(len(dates) * 0.8)
    test_start = dates[split_index]

    # Purge seven days before test period.
    # This prevents overlapping future-label windows
    # from leaking into the test period.
    train_end = (
        pd.Timestamp(test_start)
        - pd.Timedelta(days=7)
    )

    train_df = df[df["date"] < train_end].copy()
    test_df = df[df["date"] >= test_start].copy()

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET]

    X_test = test_df[FEATURES]
    y_test = test_df[TARGET]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError(
            "Training and test data must both contain "
            "positive and negative stockout cases."
        )

    print("Training records:", len(train_df))
    print("Testing records:", len(test_df))
    print("Training positive cases:", int(y_train.sum()))
    print("Testing positive cases:", int(y_test.sum()))

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

    results = []
    probabilities_by_model = {}

    for name, model in models.items():

        print(f"\nTraining {name}...")

        model.fit(X_train, y_train)

        probabilities = model.predict_proba(X_test)[:, 1]

        metrics = evaluate_model(
            y_test,
            probabilities
        )

        results.append({
            "Model": name,
            **{
                key: round(value, 4)
                for key, value in metrics.items()
            }
        })

        probabilities_by_model[name] = probabilities

        filename = (
            "logistic_stockout.joblib"
            if name == "Logistic Regression"
            else "random_forest_stockout.joblib"
        )

        joblib.dump(
            model,
            f"{MODEL_DIR}/{filename}"
        )

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        f"{OUTPUT_DIR}/stockout_model_metrics.csv",
        index=False
    )

    print("\n========== MODEL COMPARISON ==========")
    print(results_df.to_string(index=False))

    # Select the model with the highest PR-AUC
    best_index = results_df["PR_AUC"].idxmax()
    best_name = results_df.loc[best_index, "Model"]

    best_probabilities = probabilities_by_model[best_name]

    predictions_df = test_df[
        ["date", "facility_id", "medicine_id", TARGET]
    ].copy()

    predictions_df["stockout_probability"] = best_probabilities
    predictions_df["predicted_stockout"] = (
        best_probabilities >= 0.5
    ).astype(int)

    predictions_df.to_csv(
        f"{OUTPUT_DIR}/stockout_test_predictions.csv",
        index=False
    )

    print("\n========== BEST MODEL ==========")
    print("Selected model:", best_name)

    print("\nConfusion matrix:")
    print(
        confusion_matrix(
            y_test,
            (best_probabilities >= 0.5).astype(int)
        )
    )

    print("\nSaved metrics and predictions.")
    print("Stockout model training completed!")


if __name__ == "__main__":
    main()

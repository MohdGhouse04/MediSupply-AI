
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = Path("data/processed/demand_features.csv")

OUTPUT_DIR = Path("data/processed/eda")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

def load_data():

    df = pd.read_csv(INPUT_FILE)

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values("date")

    return df


# --------------------------------------------------
# SUMMARY ANALYSIS
# --------------------------------------------------

def generate_summary(df):

    print("\n========== DATASET SUMMARY ==========")

    print("Total records:", len(df))

    print("Total medicines:", df["medicine_id"].nunique())

    print("Total facilities:", df["facility_id"].nunique())

    print("Date range:")
    print(df["date"].min(), "to", df["date"].max())

    print("\n========== DEMAND SUMMARY ==========")

    print(
        df.groupby("generic_name")[
            [
                "demand_quantity",
                "fulfilled_quantity",
                "unmet_demand"
            ]
        ].sum()
    )

    print("\n========== FACILITY SUMMARY ==========")

    print(
        df.groupby("facility_name")[
            [
                "demand_quantity",
                "fulfilled_quantity",
                "unmet_demand"
            ]
        ].sum()
    )

    print("\n========== STOCKOUT SUMMARY ==========")

    print(
        df.groupby("generic_name")["stockout_flag"]
        .agg(["sum", "mean"])
    )

    print("\nOverall stockout record percentage:")

    print(
        round(df["stockout_flag"].mean() * 100, 2),
        "%"
    )

    print("\nTotal unmet demand:", df["unmet_demand"].sum())


# --------------------------------------------------
# CHART 1: MEDICINE-WISE DEMAND
# --------------------------------------------------

def plot_medicine_demand(df):

    demand = (
        df.groupby("generic_name")["demand_quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    plt.figure(figsize=(9, 5))

    demand.plot(kind="bar")

    plt.title("Total Demand by Medicine")

    plt.xlabel("Medicine")

    plt.ylabel("Demand Quantity")

    plt.xticks(rotation=30)

    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "medicine_demand.png")

    plt.close()


# --------------------------------------------------
# CHART 2: FACILITY-WISE UNMET DEMAND
# --------------------------------------------------

def plot_facility_unmet_demand(df):

    unmet = (
        df.groupby("facility_name")["unmet_demand"]
        .sum()
    )

    plt.figure(figsize=(9, 5))

    unmet.plot(kind="bar")

    plt.title("Unmet Demand by Facility")

    plt.xlabel("Facility")

    plt.ylabel("Unmet Demand")

    plt.xticks(rotation=20)

    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "facility_unmet_demand.png")

    plt.close()


# --------------------------------------------------
# CHART 3: DAILY DEMAND TREND
# --------------------------------------------------

def plot_daily_demand(df):

    daily = (
        df.groupby("date")["demand_quantity"]
        .sum()
        .sort_index()
    )

    rolling = daily.rolling(7).mean()

    plt.figure(figsize=(12, 5))

    plt.plot(
        daily.index,
        daily.values,
        label="Daily demand",
        alpha=0.4
    )

    plt.plot(
        rolling.index,
        rolling.values,
        label="7-day average"
    )

    plt.title("Daily Medicine Demand Trend")

    plt.xlabel("Date")

    plt.ylabel("Demand Quantity")

    plt.legend()

    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "daily_demand_trend.png")

    plt.close()


# --------------------------------------------------
# CHART 4: MONTHLY DEMAND
# --------------------------------------------------

def plot_monthly_demand(df):

    monthly = (
        df.groupby("month")["demand_quantity"]
        .sum()
        .reindex(range(1, 13), fill_value=0)
    )

    plt.figure(figsize=(9, 5))

    monthly.plot(kind="bar")

    plt.title("Monthly Medicine Demand")

    plt.xlabel("Month")

    plt.ylabel("Total Demand")

    plt.xticks(
        range(12),
        [
            "Jan", "Feb", "Mar", "Apr",
            "May", "Jun", "Jul", "Aug",
            "Sep", "Oct", "Nov", "Dec"
        ],
        rotation=0
    )

    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "monthly_demand.png")

    plt.close()


# --------------------------------------------------
# CHART 5: DEMAND DISTRIBUTION
# --------------------------------------------------

def plot_demand_distribution(df):

    plt.figure(figsize=(9, 5))

    plt.hist(
        df["demand_quantity"],
        bins=30
    )

    plt.title("Daily Demand Distribution")

    plt.xlabel("Demand Quantity")

    plt.ylabel("Frequency")

    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "demand_distribution.png")

    plt.close()


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("Starting MediSupply AI EDA...")

    df = load_data()

    generate_summary(df)

    plot_medicine_demand(df)

    plot_facility_unmet_demand(df)

    plot_daily_demand(df)

    plot_monthly_demand(df)

    plot_demand_distribution(df)

    print("\nEDA completed successfully!")

    print("Charts saved in:", OUTPUT_DIR)


if __name__ == "__main__":

    main()

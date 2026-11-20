
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from backend.app.database.connection import engine


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

DAYS = 365
RANDOM_SEED = 42

OUTPUT_DIR = Path("data/synthetic")
OUTPUT_FILE = OUTPUT_DIR / "daily_medicine_demand.csv"

rng = np.random.default_rng(RANDOM_SEED)

BASE_DEMAND = {
    "paracetamol": 18,
    "amoxicillin": 8,
    "cetirizine": 6,
}


# --------------------------------------------------
# FETCH FACILITIES, MEDICINES AND CURRENT STOCK
# --------------------------------------------------

def fetch_project_data():

    query = text("""
        SELECT
            f.facility_id,
            f.facility_name,
            f.facility_type,
            m.medicine_id,
            m.generic_name,
            COALESCE(SUM(
                CASE
                    WHEN mb.batch_status = 'AVAILABLE'
                    AND mb.expires_on >= CURRENT_DATE
                    THEN GREATEST(
                        i.quantity_on_hand
                        - i.reserved_quantity
                        - i.damaged_quantity, 0
                    )
                    ELSE 0
                END
            ), 0) AS usable_stock

        FROM facilities f

        CROSS JOIN medicines m

        LEFT JOIN medicine_batches mb
            ON mb.medicine_id = m.medicine_id

        LEFT JOIN inventory i
            ON i.batch_id = mb.batch_id
            AND i.facility_id = f.facility_id

        GROUP BY
            f.facility_id,
            f.facility_name,
            f.facility_type,
            m.medicine_id,
            m.generic_name

        ORDER BY f.facility_id, m.medicine_id
    """)

    with engine.connect() as connection:
        return pd.read_sql(query, connection)


# --------------------------------------------------
# DEMAND GENERATION
# --------------------------------------------------

def calculate_daily_demand(
    medicine_name,
    facility_type,
    current_date
):

    medicine = medicine_name.lower()

    base = BASE_DEMAND.get(medicine, 5)

    # Hospitals generally consume more than pharmacies.
    facility_multiplier = (
        1.7 if facility_type == "HOSPITAL" else
        1.0 if facility_type == "PHARMACY" else
        2.0
    )

    # Seasonal demand variation.
    month = current_date.month

    seasonal_multiplier = 1.0

    if medicine in ["amoxicillin", "cetirizine"]:
        if month in [6, 7, 8, 9, 12, 1]:
            seasonal_multiplier = 1.30

    if medicine == "paracetamol":
        if month in [6, 7, 8, 9]:
            seasonal_multiplier = 1.20

    # Weekend demand variation.
    weekend_multiplier = (
        1.15 if current_date.weekday() >= 5 else 1.0
    )

    mean_demand = (
        base
        * facility_multiplier
        * seasonal_multiplier
        * weekend_multiplier
    )

    # Occasional demand spikes.
    spike_flag = rng.random() < 0.02

    if spike_flag:
        mean_demand *= rng.uniform(1.5, 2.5)

    demand = max(0, int(rng.poisson(mean_demand)))

    return demand, spike_flag


# --------------------------------------------------
# SIMULATE ONE FACILITY-MEDICINE PAIR
# --------------------------------------------------

def simulate_inventory(facility, medicine, start_date, end_date):

    medicine_name = medicine["generic_name"]

    facility_type = facility["facility_type"]

    current_stock = max(
        int(facility["usable_stock"]),
        50
    )

    baseline = (
        BASE_DEMAND.get(medicine_name.lower(), 5)
        * (1.7 if facility_type == "HOSPITAL" else 1.0)
    )

    reorder_point = int(baseline * 10)
    target_stock = int(baseline * 30)

    pending_delivery = None
    records = []

    current_date = start_date

    while current_date <= end_date:

        restock_quantity = 0

        # Receive a previously scheduled delivery.
        if (
            pending_delivery is not None
            and current_date >= pending_delivery["delivery_date"]
        ):

            restock_quantity = pending_delivery["quantity"]

            current_stock += restock_quantity

            pending_delivery = None

        # Generate actual underlying demand.
        demand, spike_flag = calculate_daily_demand(
            medicine_name,
            facility_type,
            current_date
        )

        # Fulfilled demand cannot exceed available stock.
        fulfilled = min(demand, current_stock)

        unmet_demand = demand - fulfilled

        current_stock -= fulfilled

        stockout_flag = unmet_demand > 0

        # Place a replenishment order if stock is low.
        if (
            current_stock <= reorder_point
            and pending_delivery is None
        ):

            delivery_delay = int(rng.integers(3, 11))

            order_quantity = max(
                target_stock - current_stock,
                1
            )

            pending_delivery = {
                "delivery_date": current_date
                + timedelta(days=delivery_delay),

                "quantity": order_quantity
            }

        records.append({
            "date": current_date,
            "facility_id": facility["facility_id"],
            "facility_name": facility["facility_name"],
            "medicine_id": medicine["medicine_id"],
            "generic_name": medicine_name,
            "demand_quantity": demand,
            "fulfilled_quantity": fulfilled,
            "unmet_demand": unmet_demand,
            "restock_quantity": restock_quantity,
            "stock_on_hand_end": current_stock,
            "stockout_flag": int(stockout_flag),
            "demand_spike_flag": int(spike_flag),
            "is_weekend": int(current_date.weekday() >= 5)
        })

        current_date += timedelta(days=1)

    return records


# --------------------------------------------------
# MAIN GENERATOR
# --------------------------------------------------

def main():

    print("Starting MediSupply AI demand generation...")

    project_data = fetch_project_data()

    if project_data.empty:
        print("No facilities or medicines found.")
        return

    facilities = (
        project_data[
            ["facility_id", "facility_name",
             "facility_type", "usable_stock"]
        ]
        .drop_duplicates(subset=["facility_id"])
        .to_dict("records")
    )

    medicines = (
        project_data[
            ["medicine_id", "generic_name"]
        ]
        .drop_duplicates(subset=["medicine_id"])
        .to_dict("records")
    )

    end_date = date.today()
    start_date = end_date - timedelta(days=DAYS - 1)

    all_records = []

    for facility in facilities:

        for medicine in medicines:

            records = simulate_inventory(
                facility,
                medicine,
                start_date,
                end_date
            )

            all_records.extend(records)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(all_records)

    df.to_csv(OUTPUT_FILE, index=False)

    print("\nDemand generation completed!")
    print("Date range:", start_date, "to", end_date)
    print("Facilities:", len(facilities))
    print("Medicines:", len(medicines))
    print("Total records:", len(df))
    print("Stockout records:", df["stockout_flag"].sum())
    print("Unmet demand:", df["unmet_demand"].sum())
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()

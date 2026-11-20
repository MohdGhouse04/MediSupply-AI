
from datetime import date
from pathlib import Path

import pandas as pd

from sqlalchemy.orm import Session

from backend.app.models.inventory import Inventory
from backend.app.models.medicine_batch import MedicineBatch
from backend.app.models.medicine import Medicine
from backend.app.models.facility import Facility


PROJECT_ROOT = Path(__file__).resolve().parents[3]

FORECAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "multi_horizon_forecasts.csv"
)

STOCKOUT_FILE = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "stockout_alerts.csv"
)


def load_forecasts():

    if not FORECAST_FILE.exists():
        raise FileNotFoundError(
            f"Forecast file not found: {FORECAST_FILE}"
        )

    df = pd.read_csv(FORECAST_FILE)

    required_columns = {
        "date",
        "facility_id",
        "medicine_id",
        "predicted_demand",
        "horizon"
    }

    if not required_columns.issubset(df.columns):
        raise ValueError("Forecast CSV has missing columns")

    return df


def load_stockout_alerts():

    if not STOCKOUT_FILE.exists():
        return pd.DataFrame()

    return pd.read_csv(STOCKOUT_FILE)


def get_transfer_recommendations(
    db: Session,
    safety_days: int = 3
):

    if safety_days < 0:
        raise ValueError("safety_days cannot be negative")

    today = date.today()

    forecasts = load_forecasts()
    alerts = load_stockout_alerts()

    forecasts["date"] = pd.to_datetime(
        forecasts["date"]
    ).dt.date

    # Only use forecasts beginning today or later.
    forecasts = forecasts[
        forecasts["date"] >= today
    ]

    if forecasts.empty:
        return []

    # Aggregate daily demand for each facility and medicine.
    demand_7 = (
        forecasts[forecasts["horizon"] == 7]
        .groupby(["facility_id", "medicine_id"])
        ["predicted_demand"]
        .sum()
        .to_dict()
    )

    demand_30 = (
        forecasts[forecasts["horizon"] == 30]
        .groupby(["facility_id", "medicine_id"])
        ["predicted_demand"]
        .sum()
        .to_dict()
    )

    # Read current eligible batch-level inventory.
    inventory_rows = (
        db.query(
            Inventory.facility_id,
            Inventory.batch_id,
            Inventory.quantity_on_hand,
            Inventory.reserved_quantity,
            Inventory.damaged_quantity,
            MedicineBatch.medicine_id,
            MedicineBatch.batch_number,
            MedicineBatch.expires_on,
            MedicineBatch.batch_status,
            MedicineBatch.unit_cost,
            Medicine.generic_name,
            Medicine.strength,
            Facility.facility_name
        )
        .join(
            MedicineBatch,
            Inventory.batch_id == MedicineBatch.batch_id
        )
        .join(
            Medicine,
            MedicineBatch.medicine_id == Medicine.medicine_id
        )
        .join(
            Facility,
            Inventory.facility_id == Facility.facility_id
        )
        .filter(
            MedicineBatch.expires_on >= today,
            MedicineBatch.batch_status == "AVAILABLE"
        )
        .all()
    )

    # Build facility-medicine stock positions.
    positions = {}

    for row in inventory_rows:

        usable = (
            row.quantity_on_hand
            - row.reserved_quantity
            - row.damaged_quantity
        )

        if usable <= 0:
            continue

        key = (row.facility_id, row.medicine_id)

        if key not in positions:

            positions[key] = {
                "facility_id": row.facility_id,
                "facility_name": row.facility_name,
                "medicine_id": row.medicine_id,
                "medicine_name": row.generic_name,
                "strength": row.strength,
                "usable_stock": 0,
                "batches": []
            }

        positions[key]["usable_stock"] += usable

        positions[key]["batches"].append({
            "batch_id": row.batch_id,
            "batch_number": row.batch_number,
            "expires_on": row.expires_on,
            "usable_stock": usable,
            "unit_cost": (
                float(row.unit_cost)
                if row.unit_cost is not None
                else None
            )
        })

    # Calculate surplus and shortage for each facility.
    for key, position in positions.items():

        seven_day_demand = demand_7.get(key, 0)

        average_daily_demand = (
            seven_day_demand / 7
        )

        safety_stock = (
            average_daily_demand * safety_days
        )

        required_stock = (
            seven_day_demand + safety_stock
        )

        position["forecast_7_day"] = round(
            seven_day_demand, 2
        )

        position["forecast_30_day"] = round(
            demand_30.get(key, 0), 2
        )

        position["safety_stock"] = round(
            safety_stock, 2
        )

        position["required_stock"] = round(
            required_stock, 2
        )

        position["surplus"] = max(
            0,
            position["usable_stock"] - required_stock
        )

        position["shortage"] = max(
            0,
            required_stock - position["usable_stock"]
        )

        position["procurement_gap_30_day"] = max(
            0,
            position["forecast_30_day"]
            - position["usable_stock"]
        )

        position["batches"].sort(
            key=lambda batch: batch["expires_on"]
        )

    recommendations = []

    # Match source facilities with destination facilities.
    medicine_ids = {
        position["medicine_id"]
        for position in positions.values()
    }

    for medicine_id in medicine_ids:

        sources = [
            position
            for position in positions.values()
            if position["medicine_id"] == medicine_id
            and position["surplus"] > 0
        ]

        destinations = [
            position
            for position in positions.values()
            if position["medicine_id"] == medicine_id
            and position["shortage"] > 0
        ]

        for destination in destinations:

            remaining_deficit = destination["shortage"]

            for source in sources:

                if remaining_deficit <= 0:
                    break

                if (
                    source["facility_id"]
                    == destination["facility_id"]
                ):
                    continue

                transferable = min(
                    source["surplus"],
                    remaining_deficit
                )

                if transferable <= 0:
                    continue

                remaining_quantity = int(
                    transferable
                )

                # Allocate batches using FEFO.
                for batch in source["batches"]:

                    if remaining_quantity <= 0:
                        break

                    # Avoid batches expiring during the
                    # immediate seven-day forecast window.
                    if (
                        batch["expires_on"] - today
                    ).days < 7:
                        continue

                    batch_quantity = min(
                        batch["usable_stock"],
                        remaining_quantity
                    )

                    if batch_quantity <= 0:
                        continue

                    recommendations.append({

    "recommendation_type": "TRANSFER_RECOMMENDED",

    "medicine_id": medicine_id,
    "medicine_name": source["medicine_name"],
    "strength": source["strength"],

    "source_facility_id": source["facility_id"],
    "source_facility": source["facility_name"],

    "destination_facility_id": destination["facility_id"],
    "destination_facility": destination["facility_name"],

    "batch_id": batch["batch_id"],
    "batch_number": batch["batch_number"],
    "batch_expiry": batch["expires_on"].isoformat(),

    "recommended_quantity": int(batch_quantity),

    "source_usable_stock": source["usable_stock"],

    "source_surplus_before_allocation":
        round(source["surplus"], 2),

    "source_surplus_after_allocation":
        round(source["surplus"] - batch_quantity, 2),

    "destination_usable_stock":
        destination["usable_stock"],

    "destination_shortage_before_allocation":
        round(remaining_deficit, 2),

    "destination_shortage_after_allocation":
        round(max(0, remaining_deficit - batch_quantity), 2),

    "destination_7_day_demand":
        destination["forecast_7_day"],

    "source_7_day_demand":
        source["forecast_7_day"],

    "source_30_day_demand":
        source["forecast_30_day"],

    "destination_30_day_demand":
        destination["forecast_30_day"],

    "destination_30_day_procurement_gap":
        destination["procurement_gap_30_day"],

    "safety_stock_days": safety_days,

    "stockout_probability": None,

    "reason":
        "Source has stock above its 7-day demand and safety buffer. "
        "Destination has a projected 7-day shortage. "
        "Batch selected using FEFO.",

    "approval_required": True

})
                    

                    source["surplus"] -= batch_quantity
                    remaining_deficit -= batch_quantity
                    remaining_quantity -= batch_quantity

    # Add historical stockout evidence.
    if not alerts.empty:

        for recommendation in recommendations:

            matching = alerts[
                (
                    alerts["facility_id"]
                    == recommendation["destination_facility_id"]
                )
                & (
                    alerts["medicine_id"]
                    == recommendation["medicine_id"]
                )
            ]

            if not matching.empty:

                alert = matching.iloc[0]

                recommendation["stockout_probability"] = round(
                    float(alert["stockout_probability"]),
                    4
                )

                recommendation["stockout_alert_date"] = str(
                    alert["date"]
                )

                recommendation["stockout_alert_is_historical"] = True

    return recommendations

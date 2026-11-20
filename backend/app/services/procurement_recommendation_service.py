
from datetime import date
from pathlib import Path
import math

import pandas as pd

from sqlalchemy.orm import Session

from backend.app.models import (
    Inventory,
    MedicineBatch,
    Medicine,
    Facility,
    StockTransfer
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

FORECAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "multi_horizon_forecasts.csv"
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
        raise ValueError(
            "Forecast file is missing required columns"
        )

    df["date"] = pd.to_datetime(df["date"]).dt.date

    return df


def get_procurement_recommendations(
    db: Session,
    safety_days: int = 3
):

    if safety_days < 0 or safety_days > 30:
        raise ValueError(
            "safety_days must be between 0 and 30"
        )

    today = date.today()

    forecasts = load_forecasts()

    forecasts = forecasts[
        forecasts["date"] >= today
    ]

    forecast_7 = (
        forecasts[forecasts["horizon"] == 7]
        .groupby(["facility_id", "medicine_id"])
        ["predicted_demand"]
        .sum()
        .to_dict()
    )

    forecast_14 = (
        forecasts[forecasts["horizon"] == 14]
        .groupby(["facility_id", "medicine_id"])
        ["predicted_demand"]
        .sum()
        .to_dict()
    )

    forecast_30 = (
        forecasts[forecasts["horizon"] == 30]
        .groupby(["facility_id", "medicine_id"])
        ["predicted_demand"]
        .sum()
        .to_dict()
    )

    if not forecast_30:
        return []

    # --------------------------------------------------
    # LOAD FACILITIES AND MEDICINES
    # --------------------------------------------------

    facilities = {
        facility.facility_id: facility.facility_name
        for facility in db.query(Facility).all()
    }

    medicines = {
        medicine.medicine_id: medicine
        for medicine in db.query(Medicine).all()
    }

    # --------------------------------------------------
    # LOAD CURRENT ELIGIBLE INVENTORY
    # --------------------------------------------------

    inventory_rows = (
        db.query(
            Inventory.facility_id,
            MedicineBatch.medicine_id,
            Inventory.quantity_on_hand,
            Inventory.reserved_quantity,
            Inventory.damaged_quantity
        )
        .join(
            MedicineBatch,
            Inventory.batch_id == MedicineBatch.batch_id
        )
        .filter(
            MedicineBatch.expires_on >= today,
            MedicineBatch.batch_status == "AVAILABLE"
        )
        .all()
    )

    current_stock = {}

    for row in inventory_rows:

        usable_stock = (
            row.quantity_on_hand
            - row.reserved_quantity
            - row.damaged_quantity
        )

        key = (
            row.facility_id,
            row.medicine_id
        )

        current_stock[key] = (
            current_stock.get(key, 0)
            + max(0, usable_stock)
        )

    # --------------------------------------------------
    # LOAD INBOUND AND OUTBOUND TRANSFERS BY STATUS
    # --------------------------------------------------

    transfer_rows = (
        db.query(
            StockTransfer.source_facility_id,
            StockTransfer.destination_facility_id,
            MedicineBatch.medicine_id,
            StockTransfer.quantity,
            StockTransfer.status
        )
        .join(
            MedicineBatch,
            StockTransfer.batch_id == MedicineBatch.batch_id
        )
        .filter(
            StockTransfer.status.in_([
                "PENDING",
                "APPROVED",
                "DISPATCHED"
            ])
        )
        .all()
    )

    inbound_by_status = {}
    approved_outbound = {}

    for row in transfer_rows:

        medicine_id = row.medicine_id
        quantity = int(row.quantity)

        # Track inbound stock by transfer status
        inbound_key = (
            row.destination_facility_id,
            medicine_id,
            row.status
        )

        inbound_by_status[inbound_key] = (
            inbound_by_status.get(inbound_key, 0)
            + quantity
        )

        # Approved outgoing stock is committed
        if row.status == "APPROVED":

            outbound_key = (
                row.source_facility_id,
                medicine_id
            )

            approved_outbound[outbound_key] = (
                approved_outbound.get(outbound_key, 0)
                + quantity
            )

    # --------------------------------------------------
    # GENERATE PROCUREMENT RECOMMENDATIONS
    # --------------------------------------------------

    recommendations = []

    for key, demand_30 in forecast_30.items():

        facility_id, medicine_id = key

        medicine = medicines.get(medicine_id)

        if medicine is None:
            continue

        usable_stock = current_stock.get(key, 0)

        approved_outgoing_quantity = approved_outbound.get(
            key,
            0
        )

        # Exclude stock committed to approved transfers
        planning_available_stock = max(
            0,
            usable_stock - approved_outgoing_quantity
        )

        demand_7 = forecast_7.get(key, 0)
        demand_14 = forecast_14.get(key, 0)

        average_daily_demand = demand_30 / 30

        safety_stock = (
            average_daily_demand * safety_days
        )

        required_stock = (
            demand_30 + safety_stock
        )

        # --------------------------------------------------
        # GROSS PROCUREMENT REQUIREMENT
        # --------------------------------------------------

        gross_gap = max(
            0,
            required_stock - planning_available_stock
        )

        gross_procurement_quantity = math.ceil(
            gross_gap
        )

        # --------------------------------------------------
        # INBOUND TRANSFER BREAKDOWN
        # --------------------------------------------------

        pending_inbound_quantity = inbound_by_status.get(
            (facility_id, medicine_id, "PENDING"),
            0
        )

        approved_inbound_quantity = inbound_by_status.get(
            (facility_id, medicine_id, "APPROVED"),
            0
        )

        dispatched_inbound_quantity = inbound_by_status.get(
            (facility_id, medicine_id, "DISPATCHED"),
            0
        )

        total_potential_inbound = (
            pending_inbound_quantity
            + approved_inbound_quantity
            + dispatched_inbound_quantity
        )

        # Only dispatched transfers reduce the provisional
        # procurement requirement.
        provisional_gap = max(
            0,
            gross_gap - dispatched_inbound_quantity
        )

        provisional_procurement_quantity = math.ceil(
            provisional_gap
        )

        # --------------------------------------------------
        # ESTIMATE DAYS OF STOCK COVER
        # --------------------------------------------------

        if average_daily_demand > 0:

            days_of_stock = (
                planning_available_stock
                / average_daily_demand
            )

        else:
            days_of_stock = None

        # --------------------------------------------------
        # PROCUREMENT URGENCY
        # --------------------------------------------------

        if planning_available_stock <= 0:

            urgency = "CRITICAL"

        elif days_of_stock is not None and days_of_stock <= 7:

            urgency = "CRITICAL"

        elif days_of_stock is not None and days_of_stock <= 14:

            urgency = "HIGH"

        elif days_of_stock is not None and days_of_stock <= 30:

            urgency = "MEDIUM"

        else:

            urgency = "LOW"

        # --------------------------------------------------
        # RECOMMENDATION STATUS
        # --------------------------------------------------

        if gross_procurement_quantity == 0:

            action = "NO_PROCUREMENT_REQUIRED"

        elif provisional_procurement_quantity == 0:

            action = "REVIEW_DISPATCHED_TRANSFER"

        else:

            action = "PROCUREMENT_RECOMMENDED"

        # --------------------------------------------------
        # FINAL RECOMMENDATION
        # --------------------------------------------------

        recommendations.append({

            "facility_id": facility_id,

            "facility_name": facilities.get(
                facility_id,
                "Unknown Facility"
            ),

            "medicine_id": medicine_id,

            "medicine_name": medicine.generic_name,

            "strength": medicine.strength,

            "unit": medicine.unit,

            "usable_stock": usable_stock,

            "planning_available_stock": planning_available_stock,

            "approved_outgoing_transfer_quantity":
                approved_outgoing_quantity,

            "forecast_7_day": round(demand_7, 2),

            "forecast_14_day": round(demand_14, 2),

            "forecast_30_day": round(demand_30, 2),

            "average_daily_demand": round(
                average_daily_demand,
                2
            ),

            "safety_stock": round(
                safety_stock,
                2
            ),

            "required_stock": round(
                required_stock,
                2
            ),

            "days_of_stock": (
                round(days_of_stock, 2)
                if days_of_stock is not None
                else None
            ),

            "gross_procurement_gap": round(
                gross_gap,
                2
            ),

            "recommended_procurement_quantity":
                gross_procurement_quantity,

            "pending_inbound_transfer_quantity":
                pending_inbound_quantity,

            "approved_inbound_transfer_quantity":
                approved_inbound_quantity,

            "dispatched_inbound_transfer_quantity":
                dispatched_inbound_quantity,

            "potential_inbound_transfer_quantity":
                total_potential_inbound,

            "provisional_procurement_quantity_after_transfers":
                provisional_procurement_quantity,

            "urgency": urgency,

            "action": action,

            "safety_stock_days": safety_days,

            "approval_required": True,

            "forecast_is_synthetic": True

        })

    # --------------------------------------------------
    # SORT BY PROCUREMENT URGENCY
    # --------------------------------------------------

    urgency_order = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4
    }

    recommendations.sort(
        key=lambda item: (
            urgency_order[item["urgency"]],
            -item["gross_procurement_gap"]
        )
    )

    return recommendations

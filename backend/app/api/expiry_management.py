
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.database.connection import get_db
from backend.app.models import (
    Inventory,
    Facility,
    Medicine,
    MedicineBatch
)

from backend.app.services.expiry_forecasting import (
    simulate_fefo_wastage
)


router = APIRouter(
    prefix="/expiry-management",
    tags=["Expiry Management"]
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

FORECAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "multi_horizon_forecasts.csv"
)


def load_60_day_forecasts():

    if not FORECAST_FILE.exists():
        return {}

    forecasts = defaultdict(dict)

    with open(FORECAST_FILE, "r", newline="") as file:

        reader = csv.DictReader(file)

        for row in reader:

            if int(row["horizon"]) != 60:
                continue

            key = (
                int(row["facility_id"]),
                int(row["medicine_id"])
            )

            forecast_date = date.fromisoformat(row["date"])

            forecasts[key][forecast_date] = float(
                row["predicted_demand"]
            )

    return forecasts


@router.get("/recommendations")
def get_expiry_recommendations(
    db: Session = Depends(get_db)
):

    today = date.today()

    statement = (
        select(
            Facility.facility_id,
            Facility.facility_name,
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength,
            MedicineBatch.batch_id,
            MedicineBatch.batch_number,
            MedicineBatch.expires_on,
            MedicineBatch.unit_cost,
            Inventory.quantity_on_hand,
            Inventory.reserved_quantity,
            Inventory.damaged_quantity
        )
        .select_from(Inventory)
        .join(
            Facility,
            Inventory.facility_id == Facility.facility_id
        )
        .join(
            MedicineBatch,
            Inventory.batch_id == MedicineBatch.batch_id
        )
        .join(
            Medicine,
            MedicineBatch.medicine_id == Medicine.medicine_id
        )
        .where(
            MedicineBatch.expires_on >= today,
            MedicineBatch.batch_status == "AVAILABLE"
        )
        .order_by(
            Facility.facility_id,
            Medicine.medicine_id,
            MedicineBatch.expires_on
        )
    )

    rows = db.execute(statement).mappings().all()

    groups = defaultdict(list)

    for row in rows:

        usable_stock = (
            row["quantity_on_hand"]
            - row["reserved_quantity"]
            - row["damaged_quantity"]
        )

        if usable_stock <= 0:
            continue

        key = (
            row["facility_id"],
            row["medicine_id"]
        )

        groups[key].append({
            **dict(row),
            "usable_stock": usable_stock,
            "remaining_stock": usable_stock,
            "projected_wastage": None
        })

    forecasts = load_60_day_forecasts()

    recommendations = []

    for key, batches in groups.items():

        facility_id, medicine_id = key

        forecast = forecasts.get(key, {})

        forecast_dates = sorted(forecast.keys())

        if not forecast_dates:

            for batch in batches:

                recommendations.append({
                    "facility_id": facility_id,
                    "facility_name": batch["facility_name"],
                    "medicine_id": medicine_id,
                    "generic_name": batch["generic_name"],
                    "strength": batch["strength"],
                    "batch_id": batch["batch_id"],
                    "batch_number": batch["batch_number"],
                    "expires_on": batch["expires_on"],
                    "usable_stock": batch["usable_stock"],
                    "projected_wastage_units": None,
                    "estimated_wastage_value": None,
                    "forecast_status": "NO_FORECAST_AVAILABLE",
                    "recommendation": "REVIEW_FEFO_AND_MONITOR"
                })

            continue

        first_forecast_date = forecast_dates[0]
        last_forecast_date = forecast_dates[-1]

        # Use the independently tested FEFO forecasting service.
        batch_forecasts = simulate_fefo_wastage(
            batches,
            forecast
        )

        for batch in batches:
            batch_result = batch_forecasts[batch["batch_id"]]

            projected_wastage = batch_result[
                "projected_wastage_units"
            ]

            forecast_status = batch_result["forecast_status"]

            if projected_wastage is None:
                    projected_wastage = batch["remaining_stock"]

                forecast_status = (
                    "ESTIMATED_WITHIN_60_DAY_FORECAST"
                )

            # Forecast does not cover the batch expiry date.
            else:

                projected_wastage = None

                forecast_status = (
                    "INSUFFICIENT_FORECAST_HORIZON"
                )

            if projected_wastage is None:

                estimated_value = None

                action = "REVIEW_FEFO_AND_MONITOR"

            else:

                if batch["unit_cost"] is not None:

                    estimated_value = round(
                        float(batch["unit_cost"])
                        * projected_wastage,
                        2
                    )

                else:

                    estimated_value = None

                if projected_wastage > 0:

                    action = "PRIORITIZE_ISSUE_OR_TRANSFER"

                else:

                    action = "NORMAL_FEFO_ISSUING"

            recommendations.append({
                "facility_id": facility_id,
                "facility_name": batch["facility_name"],
                "medicine_id": medicine_id,
                "generic_name": batch["generic_name"],
                "strength": batch["strength"],
                "batch_id": batch["batch_id"],
                "batch_number": batch["batch_number"],
                "expires_on": expiry_date,
                "usable_stock": batch["usable_stock"],
                "projected_wastage_units": projected_wastage,
                "estimated_wastage_value": estimated_value,
                "forecast_status": forecast_status,
                "recommendation": action
            })

    known_records = [
        item for item in recommendations
        if item["projected_wastage_units"] is not None
    ]

    return {
        "forecast_model": "60-day demand forecast (experimental)",
        "forecast_horizon_days": 60,
        "forecast_file": str(FORECAST_FILE.name),
        "total_batches_reviewed": len(recommendations),
        "batches_with_insufficient_forecast": sum(
            1 for item in recommendations
            if item["projected_wastage_units"] is None
        ),
        "estimated_wastage_units": sum(
            item["projected_wastage_units"]
            for item in known_records
        ),
        "estimated_wastage_value": round(
            sum(
                item["estimated_wastage_value"] or 0
                for item in known_records
            ),
            2
        ),
        "recommendations": recommendations
    }

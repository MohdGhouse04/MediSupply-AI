import csv
from pathlib import Path
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query


router = APIRouter(
    prefix="/demand-forecasts",
    tags=["Demand Forecasts"]
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

FORECAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "multi_horizon_forecasts.csv"
)

SUPPORTED_HORIZONS = {7, 14, 30, 60}


@router.get("/")
def get_demand_forecasts(
    horizon: int = Query(default=7),
    facility_id: int | None = Query(default=None, ge=1),
    medicine_id: int | None = Query(default=None, ge=1),
):
    if horizon not in SUPPORTED_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail="Horizon must be one of: 7, 14, 30, 60"
        )

    if not FORECAST_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="Demand forecast file is not available"
        )

    forecasts = []
    totals_by_facility = defaultdict(float)
    totals_by_medicine = defaultdict(float)

    try:
        with open(FORECAST_FILE, "r", newline="") as file:
            reader = csv.DictReader(file)

            required_columns = {
                "date",
                "facility_id",
                "medicine_id",
                "forecast_day",
                "predicted_demand",
                "horizon",
            }

            if not required_columns.issubset(set(reader.fieldnames or [])):
                raise HTTPException(
                    status_code=500,
                    detail="Forecast file has an invalid schema"
                )

            for row in reader:
                if int(row["horizon"]) != horizon:
                    continue

                current_facility = int(row["facility_id"])
                current_medicine = int(row["medicine_id"])

                if facility_id is not None and current_facility != facility_id:
                    continue

                if medicine_id is not None and current_medicine != medicine_id:
                    continue

                demand = float(row["predicted_demand"])

                if demand < 0:
                    raise ValueError("Negative predicted demand found")

                record = {
                    "date": row["date"],
                    "facility_id": current_facility,
                    "medicine_id": current_medicine,
                    "forecast_day": int(row["forecast_day"]),
                    "predicted_demand": round(demand, 2),
                    "horizon": horizon,
                }

                forecasts.append(record)
                totals_by_facility[current_facility] += demand
                totals_by_medicine[current_medicine] += demand

    except HTTPException:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read forecast data: {str(exc)}"
        )

    forecasts.sort(
        key=lambda item: (
            item["date"],
            item["facility_id"],
            item["medicine_id"]
        )
    )

    total_demand = sum(item["predicted_demand"] for item in forecasts)
    unique_dates = sorted({item["date"] for item in forecasts})

    return {
        "horizon_days": horizon,
        "total_records": len(forecasts),
        "total_predicted_demand": round(total_demand, 2),
        "average_daily_demand": (
            round(total_demand / len(unique_dates), 2)
            if unique_dates else 0
        ),
        "forecast_start_date": unique_dates[0] if unique_dates else None,
        "forecast_end_date": unique_dates[-1] if unique_dates else None,
        "filters": {
            "facility_id": facility_id,
            "medicine_id": medicine_id,
        },
        "facility_totals": [
            {
                "facility_id": key,
                "predicted_demand": round(value, 2)
            }
            for key, value in sorted(totals_by_facility.items())
        ],
        "medicine_totals": [
            {
                "medicine_id": key,
                "predicted_demand": round(value, 2)
            }
            for key, value in sorted(totals_by_medicine.items())
        ],
        "forecasts": forecasts,
    }

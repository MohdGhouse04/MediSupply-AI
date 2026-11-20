
from pathlib import Path

import pandas as pd

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db


router = APIRouter(
    prefix="/stockout-alerts",
    tags=["Stockout Alerts"]
)

ROOT = Path(__file__).resolve().parents[3]

ALERTS_PATH = ROOT / "ml/data/stockout_alerts.csv"


@router.get("/")
def get_stockout_alerts(
    db: Session = Depends(get_db)
):
    """
    Return stockout alerts with facility and medicine details.
    """

    if not ALERTS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Stockout alerts file not found. Generate alerts first."
        )

    try:
        alerts_df = pd.read_csv(ALERTS_PATH)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read stockout alerts: {str(exc)}"
        )

    if alerts_df.empty:
        return {
            "total_alerts": 0,
            "high_risk_count": 0,
            "low_risk_count": 0,
            "alerts": []
        }

    # Fetch facility names
    facilities = db.execute(
        text("""
            SELECT facility_id, facility_name
            FROM facilities
        """)
    ).mappings().all()

    facility_lookup = {
        row["facility_id"]: row["facility_name"]
        for row in facilities
    }

    # Fetch medicine details
    medicines = db.execute(
        text("""
            SELECT
                medicine_id,
                generic_name,
                strength,
                dosage_form
            FROM medicines
        """)
    ).mappings().all()

    medicine_lookup = {
        row["medicine_id"]: {
            "generic_name": row["generic_name"],
            "strength": row["strength"],
            "dosage_form": row["dosage_form"]
        }
        for row in medicines
    }

    results = []

    for _, row in alerts_df.iterrows():

        facility_id = int(row["facility_id"])
        medicine_id = int(row["medicine_id"])

        medicine = medicine_lookup.get(medicine_id)

        results.append({
            "date": str(row["date"]),

            "facility_id": facility_id,
            "facility_name": facility_lookup.get(
                facility_id,
                "Unknown Facility"
            ),

            "medicine_id": medicine_id,
            "medicine": (
                medicine["generic_name"]
                if medicine else "Unknown Medicine"
            ),
            "strength": (
                medicine["strength"]
                if medicine else None
            ),
            "dosage_form": (
                medicine["dosage_form"]
                if medicine else None
            ),

            "stockout_probability": float(
                row["stockout_probability"]
            ),
            "risk_threshold": float(
                row["risk_threshold"]
            ),
            "risk_status": row["risk_status"],
            "alert_action": row["alert_action"],

            "previous_stock": int(
                row["previous_stock"]
            ),
            "previous_unmet_demand": float(
                row["previous_unmet_demand"]
            ),

            "average_demand_7_days": float(
                row["demand_rolling_mean_7"]
            ),
            "average_demand_14_days": float(
                row["demand_rolling_mean_14"]
            ),
            "average_demand_30_days": float(
                row["demand_rolling_mean_30"]
            )
        })

    high_risk_count = sum(
        alert["risk_status"] == "HIGH_RISK"
        for alert in results
    )

    low_risk_count = sum(
        alert["risk_status"] == "LOW_RISK"
        for alert in results
    )

    return {
        "total_alerts": len(results),
        "high_risk_count": high_risk_count,
        "low_risk_count": low_risk_count,
        "source_date": str(alerts_df["date"].max()),
        "alerts": results
    }

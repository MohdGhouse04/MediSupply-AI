import csv
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models.stockout_alert import StockoutAlert
from backend.app.models.facility import Facility
from backend.app.models.medicine import Medicine


router = APIRouter(
    prefix="/stockout-alerts",
    tags=["Stockout Alerts"],
)

ROOT = Path(__file__).resolve().parents[3]
ALERTS_PATH = ROOT / "ml/data/stockout_alerts.csv"

MAX_ALERT_AGE_DAYS = 2
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

REQUIRED_COLUMNS = {
    "date",
    "facility_id",
    "medicine_id",
    "stockout_probability",
    "risk_threshold",
    "risk_status",
    "alert_action",
    "previous_stock",
    "previous_unmet_demand",
    "demand_rolling_mean_7",
    "demand_rolling_mean_14",
    "demand_rolling_mean_30",
}


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(min_length=1, max_length=150)


def get_freshness(source_date: date):
    today = datetime.now(INDIA_TIMEZONE).date()
    age = (today - source_date).days

    if age < 0:
        status = "FUTURE_DATED"
    elif age > MAX_ALERT_AGE_DAYS:
        status = "STALE"
    else:
        status = "FRESH"

    return {
        "source_age_days": age,
        "freshness_status": status,
        "is_stale": status != "FRESH",
    }


def serialize_alert(row):
    alert, facility_name, medicine_name, strength, dosage_form = row

    freshness = get_freshness(alert.source_date)

    return {
        "alert_id": alert.alert_id,
        "date": alert.source_date.isoformat(),

        "facility_id": alert.facility_id,
        "facility_name": facility_name,

        "medicine_id": alert.medicine_id,
        "medicine": medicine_name,
        "strength": strength,
        "dosage_form": dosage_form,

        "stockout_probability": float(alert.stockout_probability),
        "risk_threshold": float(alert.risk_threshold),
        "risk_status": alert.risk_status,
        "alert_action": alert.alert_action,

        "previous_stock": alert.previous_stock,
        "previous_unmet_demand": alert.previous_unmet_demand,

        "average_demand_7_days": float(alert.demand_rolling_mean_7),
        "average_demand_14_days": float(alert.demand_rolling_mean_14),
        "average_demand_30_days": float(alert.demand_rolling_mean_30),

        "acknowledged": alert.acknowledged,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": (
            alert.acknowledged_at.isoformat()
            if alert.acknowledged_at else None
        ),

        **freshness,
    }


def alert_query():
    return (
        select(
            StockoutAlert,
            Facility.facility_name,
            Medicine.generic_name,
            Medicine.strength,
            Medicine.dosage_form,
        )
        .join(
            Facility,
            Facility.facility_id == StockoutAlert.facility_id,
        )
        .join(
            Medicine,
            Medicine.medicine_id == StockoutAlert.medicine_id,
        )
    )


@router.post("/sync")
def sync_stockout_alerts(db: Session = Depends(get_db)):
    """Import generated CSV predictions into PostgreSQL."""

    if not ALERTS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Stockout alerts CSV not found. Generate predictions first.",
        )

    try:
        with ALERTS_PATH.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise ValueError("CSV has no header.")

            missing = REQUIRED_COLUMNS - set(reader.fieldnames)

            if missing:
                raise ValueError(
                    f"Missing required CSV columns: {sorted(missing)}"
                )

            records = []

            for row in reader:
                records.append({
                    "source_date": date.fromisoformat(row["date"][:10]),
                    "facility_id": int(row["facility_id"]),
                    "medicine_id": int(row["medicine_id"]),
                    "stockout_probability": float(row["stockout_probability"]),
                    "risk_threshold": float(row["risk_threshold"]),
                    "risk_status": row["risk_status"],
                    "alert_action": row["alert_action"],
                    "previous_stock": int(float(row["previous_stock"])),
                    "previous_unmet_demand": int(
                        float(row["previous_unmet_demand"])
                    ),
                    "demand_rolling_mean_7": float(
                        row["demand_rolling_mean_7"]
                    ),
                    "demand_rolling_mean_14": float(
                        row["demand_rolling_mean_14"]
                    ),
                    "demand_rolling_mean_30": float(
                        row["demand_rolling_mean_30"]
                    ),
                })

        if not records:
            raise ValueError("CSV contains no alert records.")

        statement = insert(StockoutAlert).values(records)

        statement = statement.on_conflict_do_update(
            constraint="uq_stockout_alert_facility_medicine_date",
            set_={
                "stockout_probability": statement.excluded.stockout_probability,
                "risk_threshold": statement.excluded.risk_threshold,
                "risk_status": statement.excluded.risk_status,
                "alert_action": statement.excluded.alert_action,
                "previous_stock": statement.excluded.previous_stock,
                "previous_unmet_demand": statement.excluded.previous_unmet_demand,
                "demand_rolling_mean_7": statement.excluded.demand_rolling_mean_7,
                "demand_rolling_mean_14": statement.excluded.demand_rolling_mean_14,
                "demand_rolling_mean_30": statement.excluded.demand_rolling_mean_30,
            },
        )

        result = db.execute(statement)
        db.commit()

        return {
            "message": "Stockout alerts synchronized successfully.",
            "processed_records": len(records),
            "database_rows_affected": result.rowcount,
            "acknowledgements_preserved": True,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Stockout alert synchronization failed: {str(exc)}",
        )


@router.get("/")
def get_stockout_alerts(db: Session = Depends(get_db)):
    """Return the latest database-backed stockout alerts."""

    rows = db.execute(
        alert_query().order_by(
            StockoutAlert.source_date.desc(),
            StockoutAlert.alert_id.desc(),
        )
    ).all()

    alerts = [serialize_alert(row) for row in rows]

    if not alerts:
        return {
            "total_alerts": 0,
            "high_risk_count": 0,
            "low_risk_count": 0,
            "acknowledged_count": 0,
            "unacknowledged_count": 0,
            "source_date": None,
            "source_age_days": None,
            "max_allowed_age_days": MAX_ALERT_AGE_DAYS,
            "freshness_status": "NO_DATA",
            "is_stale": True,
            "alerts": [],
        }

    latest_date = max(
        date.fromisoformat(alert["date"]) for alert in alerts
    )
    freshness = get_freshness(latest_date)

    return {
        "total_alerts": len(alerts),
        "high_risk_count": sum(
            alert["risk_status"] == "HIGH_RISK" for alert in alerts
        ),
        "low_risk_count": sum(
            alert["risk_status"] == "LOW_RISK" for alert in alerts
        ),
        "acknowledged_count": sum(
            alert["acknowledged"] for alert in alerts
        ),
        "unacknowledged_count": sum(
            not alert["acknowledged"] for alert in alerts
        ),
        "source_date": latest_date.isoformat(),
        "source_age_days": freshness["source_age_days"],
        "max_allowed_age_days": MAX_ALERT_AGE_DAYS,
        "freshness_status": freshness["freshness_status"],
        "is_stale": freshness["is_stale"],
        "alerts": alerts,
    }


@router.get("/history")
def get_stockout_alert_history(
    facility_id: int | None = Query(default=None, gt=0),
    medicine_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    """Retrieve historical alerts with optional filters."""

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be later than end_date.",
        )

    statement = alert_query()

    if facility_id is not None:
        statement = statement.where(
            StockoutAlert.facility_id == facility_id
        )

    if medicine_id is not None:
        statement = statement.where(
            StockoutAlert.medicine_id == medicine_id
        )

    if start_date is not None:
        statement = statement.where(
            StockoutAlert.source_date >= start_date
        )

    if end_date is not None:
        statement = statement.where(
            StockoutAlert.source_date <= end_date
        )

    rows = db.execute(
        statement.order_by(
            StockoutAlert.source_date.desc(),
            StockoutAlert.alert_id.desc(),
        )
    ).all()

    alerts = [serialize_alert(row) for row in rows]

    return {
        "total_records": len(alerts),
        "filters": {
            "facility_id": facility_id,
            "medicine_id": medicine_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "alerts": alerts,
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge_stockout_alert(
    alert_id: int,
    request: AcknowledgeRequest,
    db: Session = Depends(get_db),
):
    """Record that an operator has reviewed an alert."""

    alert = db.get(StockoutAlert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail=f"Stockout alert {alert_id} not found.",
        )

    if alert.acknowledged:
        return {
            "message": "Alert was already acknowledged.",
            "alert_id": alert.alert_id,
            "acknowledged": True,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": (
                alert.acknowledged_at.isoformat()
                if alert.acknowledged_at else None
            ),
        }

    acknowledged_by = request.acknowledged_by.strip()

    if not acknowledged_by:
        raise HTTPException(
            status_code=422,
            detail="acknowledged_by cannot be blank.",
        )

    alert.acknowledged = True
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    db.commit()
    db.refresh(alert)

    return {
        "message": "Stockout alert acknowledged successfully.",
        "alert_id": alert.alert_id,
        "acknowledged": alert.acknowledged,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at.isoformat(),
    }

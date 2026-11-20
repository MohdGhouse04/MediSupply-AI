
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, case, and_
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models import (
    Inventory,
    Facility,
    MedicineBatch,
    Medicine
)


router = APIRouter(
    prefix="/fefo",
    tags=["FEFO Recommendations"]
)


@router.get("/recommendations")
def get_fefo_recommendations(
    facility_id: int | None = Query(default=None, ge=1),
    medicine_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db)
):
    """
    Recommend the order in which eligible medicine batches
    should be issued, based on earliest expiry date.
    """

    today = date.today()

    usable_stock = case(
        (
            and_(
                MedicineBatch.expires_on >= today,
                MedicineBatch.batch_status == "AVAILABLE"
            ),
            (
                Inventory.quantity_on_hand
                - Inventory.reserved_quantity
                - Inventory.damaged_quantity
            )
        ),
        else_=0
    )

    statement = (
        select(
            Facility.facility_id,
            Facility.facility_name,

            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength,
            Medicine.dosage_form,

            MedicineBatch.batch_id,
            MedicineBatch.batch_number,
            MedicineBatch.expires_on,
            MedicineBatch.batch_status,

            Inventory.quantity_on_hand,
            Inventory.reserved_quantity,
            Inventory.damaged_quantity,

            usable_stock.label("usable_stock")
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
            MedicineBatch.batch_status == "AVAILABLE",
            usable_stock > 0
        )
    )

    if facility_id is not None:

        if db.get(Facility, facility_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Facility not found"
            )

        statement = statement.where(
            Facility.facility_id == facility_id
        )

    if medicine_id is not None:

        if db.get(Medicine, medicine_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Medicine not found"
            )

        statement = statement.where(
            Medicine.medicine_id == medicine_id
        )

    statement = statement.order_by(
        Facility.facility_name,
        Medicine.generic_name,
        Medicine.strength,
        MedicineBatch.expires_on,
        MedicineBatch.batch_id
    )

    rows = db.execute(statement).mappings().all()

    recommendations = []
    priority_tracker = {}

    for row in rows:

        group_key = (
            row["facility_id"],
            row["medicine_id"]
        )

        priority_tracker[group_key] = (
            priority_tracker.get(group_key, 0) + 1
        )

        days_to_expiry = (
            row["expires_on"] - today
        ).days

        recommendations.append({

            "facility_id": row["facility_id"],
            "facility_name": row["facility_name"],

            "medicine_id": row["medicine_id"],
            "medicine_name": row["generic_name"],
            "strength": row["strength"],
            "dosage_form": row["dosage_form"],

            "batch_id": row["batch_id"],
            "batch_number": row["batch_number"],

            "expires_on": str(row["expires_on"]),
            "days_to_expiry": days_to_expiry,

            "quantity_on_hand": row["quantity_on_hand"],
            "reserved_quantity": row["reserved_quantity"],
            "damaged_quantity": row["damaged_quantity"],
            "usable_stock": row["usable_stock"],

            "issue_priority": priority_tracker[group_key],

            "recommendation": (
                "ISSUE_FIRST"
                if priority_tracker[group_key] == 1
                else "ISSUE_AFTER_EARLIER_BATCHES"
            )
        })

    return {
        "total_eligible_batches": len(recommendations),
        "facility_filter": facility_id,
        "medicine_filter": medicine_id,
        "generated_date": str(today),
        "recommendations": recommendations
    }

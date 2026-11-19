
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, case, and_, func

from backend.app.database.connection import get_db
from backend.app.models import (
    Inventory,
    Facility,
    MedicineBatch,
    Medicine
)
from backend.app.schemas.inventory import InventoryResponse


router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


# Calculate usable stock only for valid medicine batches
def calculate_usable_stock():

    return case(
        (
            and_(
                MedicineBatch.expires_on >= date.today(),
                MedicineBatch.batch_status == "AVAILABLE"
            ),
            (
                Inventory.quantity_on_hand
                - Inventory.reserved_quantity
                - Inventory.damaged_quantity
            )
        ),
        else_=0
    ).label("usable_stock")


# Get inventory from all facilities
@router.get("/", response_model=list[InventoryResponse])
def get_inventory(db: Session = Depends(get_db)):

    statement = (
        select(
            Facility.facility_name.label("facility_name"),
            Medicine.generic_name.label("generic_name"),
            Medicine.strength.label("strength"),
            MedicineBatch.batch_number.label("batch_number"),
            MedicineBatch.expires_on.label("expires_on"),
            Inventory.quantity_on_hand.label("quantity_on_hand"),
            Inventory.reserved_quantity.label("reserved_quantity"),
            Inventory.damaged_quantity.label("damaged_quantity"),
            calculate_usable_stock()
        )
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
        .order_by(
            Facility.facility_name,
            Medicine.generic_name
        )
    )

    results = db.execute(statement).mappings().all()

    return [dict(row) for row in results]


# Get inventory for a specific facility
@router.get("/{facility_id}", response_model=list[InventoryResponse])
def get_inventory_by_facility(
    facility_id: int,
    db: Session = Depends(get_db)
):

    statement = (
        select(
            Facility.facility_name.label("facility_name"),
            Medicine.generic_name.label("generic_name"),
            Medicine.strength.label("strength"),
            MedicineBatch.batch_number.label("batch_number"),
            MedicineBatch.expires_on.label("expires_on"),
            Inventory.quantity_on_hand.label("quantity_on_hand"),
            Inventory.reserved_quantity.label("reserved_quantity"),
            Inventory.damaged_quantity.label("damaged_quantity"),
            calculate_usable_stock()
        )
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
        .where(Facility.facility_id == facility_id)
        .order_by(Medicine.generic_name)
    )

    results = db.execute(statement).mappings().all()

    if not results:
        facility_exists = db.get(Facility, facility_id)

        if not facility_exists:
            raise HTTPException(
                status_code=404,
                detail="Facility not found"
            )

    return [dict(row) for row in results]


# Get medicine availability across all facilities
@router.get(
    "/medicine/{medicine_id}",
    response_model=list[InventoryResponse]
)
def get_medicine_availability(
    medicine_id: int,
    db: Session = Depends(get_db)
):

    statement = (
        select(
            Facility.facility_name.label("facility_name"),
            Medicine.generic_name.label("generic_name"),
            Medicine.strength.label("strength"),
            MedicineBatch.batch_number.label("batch_number"),
            MedicineBatch.expires_on.label("expires_on"),
            Inventory.quantity_on_hand.label("quantity_on_hand"),
            Inventory.reserved_quantity.label("reserved_quantity"),
            Inventory.damaged_quantity.label("damaged_quantity"),
            calculate_usable_stock()
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
        .where(Medicine.medicine_id == medicine_id)
        .order_by(Facility.facility_name)
    )

    results = db.execute(statement).mappings().all()

    if not results:
        medicine_exists = db.get(Medicine, medicine_id)

        if not medicine_exists:
            raise HTTPException(
                status_code=404,
                detail="Medicine not found"
            )

    return [dict(row) for row in results]


# Get total usable stock for each medicine across all facilities
@router.get("/summary/medicines")
def get_medicine_inventory_summary(db: Session = Depends(get_db)):

    statement = (
        select(
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength,
            func.coalesce(
                func.sum(calculate_usable_stock()),
                0
            ).label("total_usable_stock")
        )
        .join(
            MedicineBatch,
            Medicine.medicine_id == MedicineBatch.medicine_id
        )
        .join(
            Inventory,
            MedicineBatch.batch_id == Inventory.batch_id
        )
        .group_by(
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength
        )
        .order_by(Medicine.generic_name)
    )

    results = db.execute(statement).mappings().all()

    return [dict(row) for row in results]


# Detect medicines with low usable stock
@router.get("/low-stock")
def get_low_stock_inventory(
    threshold: int = Query(default=100, ge=0),
    db: Session = Depends(get_db)
):

    statement = (
        select(
            Facility.facility_id,
            Facility.facility_name,
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength,
            func.sum(
                calculate_usable_stock()
            ).label("usable_stock")
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
        .group_by(
            Facility.facility_id,
            Facility.facility_name,
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength
        )
        .having(
            func.sum(calculate_usable_stock()) < threshold
        )
        .order_by(
            func.sum(calculate_usable_stock()).asc()
        )
    )

    results = db.execute(statement).mappings().all()

    return [dict(row) for row in results]

# Detect medicine batches approaching expiry
@router.get("/expiry-risk")
def get_expiry_risk(
    days: int = Query(default=90, ge=1),
    db: Session = Depends(get_db)
):

    today = date.today()

    expiry_limit = today + timedelta(days=days)

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
            func.sum(
                calculate_usable_stock()
            ).label("usable_stock")
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
            MedicineBatch.expires_on <= expiry_limit,
            MedicineBatch.batch_status == "AVAILABLE"
        )
        .group_by(
            Facility.facility_id,
            Facility.facility_name,
            Medicine.medicine_id,
            Medicine.generic_name,
            Medicine.strength,
            MedicineBatch.batch_id,
            MedicineBatch.batch_number,
            MedicineBatch.expires_on
        )
        .having(
            func.sum(calculate_usable_stock()) > 0
        )
        .order_by(MedicineBatch.expires_on)
    )

    results = db.execute(statement).mappings().all()

    return [
        {
            **dict(row),
            "days_to_expiry": (row["expires_on"] - today).days
        }
        for row in results
    ]

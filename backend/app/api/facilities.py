
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.database.connection import get_db
from backend.app.models import Facility, Inventory, InventoryTransaction
from backend.app.schemas.facility import (
    FacilityCreate,
    FacilityUpdate,
    FacilityResponse
)


router = APIRouter(
    prefix="/facilities",
    tags=["Facilities"]
)


# CREATE FACILITY
@router.post(
    "/",
    response_model=FacilityResponse,
    status_code=status.HTTP_201_CREATED
)
def create_facility(
    facility_data: FacilityCreate,
    db: Session = Depends(get_db)
):

    facility = Facility(**facility_data.model_dump())

    db.add(facility)
    db.commit()
    db.refresh(facility)

    return facility


# GET ALL FACILITIES
@router.get(
    "/",
    response_model=list[FacilityResponse]
)
def get_all_facilities(
    db: Session = Depends(get_db)
):

    statement = select(Facility).order_by(Facility.facility_id)

    facilities = db.execute(statement).scalars().all()

    return facilities


# GET FACILITY BY ID
@router.get(
    "/{facility_id}",
    response_model=FacilityResponse
)
def get_facility_by_id(
    facility_id: int,
    db: Session = Depends(get_db)
):

    facility = db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )

    return facility


# UPDATE FACILITY
@router.put(
    "/{facility_id}",
    response_model=FacilityResponse
)
def update_facility(
    facility_id: int,
    facility_data: FacilityUpdate,
    db: Session = Depends(get_db)
):

    facility = db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )

    update_data = facility_data.model_dump()

    for key, value in update_data.items():
        setattr(facility, key, value)

    db.commit()
    db.refresh(facility)

    return facility


# DELETE FACILITY
@router.delete(
    "/{facility_id}"
)
def delete_facility(
    facility_id: int,
    db: Session = Depends(get_db)
):

    facility = db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )

    # Check whether inventory records reference this facility
    inventory_exists = db.execute(
        select(Inventory.inventory_id)
        .where(Inventory.facility_id == facility_id)
        .limit(1)
    ).first()

    # Check whether transaction records reference this facility
    transaction_exists = db.execute(
        select(InventoryTransaction.transaction_id)
        .where(InventoryTransaction.facility_id == facility_id)
        .limit(1)
    ).first()

    if inventory_exists or transaction_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete facility because inventory or transaction records reference it"
        )

    db.delete(facility)
    db.commit()

    return {
        "message": "Facility deleted successfully",
        "facility_id": facility_id
    }

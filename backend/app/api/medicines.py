
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.database.connection import get_db
from backend.app.models import Medicine
from backend.app.schemas.medicine import (
    MedicineCreate,
    MedicineUpdate,
    MedicineResponse
)


router = APIRouter(
    prefix="/medicines",
    tags=["Medicines"]
)


# CREATE MEDICINE
@router.post(
    "/",
    response_model=MedicineResponse,
    status_code=status.HTTP_201_CREATED
)
def create_medicine(
    medicine_data: MedicineCreate,
    db: Session = Depends(get_db)
):

    medicine = Medicine(**medicine_data.model_dump())

    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    return medicine


# GET ALL MEDICINES
@router.get(
    "/",
    response_model=list[MedicineResponse]
)
def get_all_medicines(
    db: Session = Depends(get_db)
):

    statement = select(Medicine).order_by(Medicine.medicine_id)

    medicines = db.execute(statement).scalars().all()

    return medicines


# GET MEDICINE BY ID
@router.get(
    "/{medicine_id}",
    response_model=MedicineResponse
)
def get_medicine_by_id(
    medicine_id: int,
    db: Session = Depends(get_db)
):

    medicine = db.get(Medicine, medicine_id)

    if medicine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )

    return medicine


# UPDATE MEDICINE
@router.put(
    "/{medicine_id}",
    response_model=MedicineResponse
)
def update_medicine(
    medicine_id: int,
    medicine_data: MedicineUpdate,
    db: Session = Depends(get_db)
):

    medicine = db.get(Medicine, medicine_id)

    if medicine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )

    update_data = medicine_data.model_dump()

    for key, value in update_data.items():
        setattr(medicine, key, value)

    db.commit()
    db.refresh(medicine)

    return medicine


# DELETE MEDICINE
@router.delete(
    "/{medicine_id}",
    status_code=status.HTTP_200_OK
)
def delete_medicine(
    medicine_id: int,
    db: Session = Depends(get_db)
):

    medicine = db.get(Medicine, medicine_id)

    if medicine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )

    db.delete(medicine)
    db.commit()

    return {
        "message": "Medicine deleted successfully",
        "medicine_id": medicine_id
    }

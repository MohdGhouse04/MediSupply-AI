
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.database.connection import get_db
from backend.app.models import (
    MedicineBatch,
    Medicine,
    Supplier,
    Inventory,
    InventoryTransaction
)

from backend.app.schemas.medicine_batch import (
    MedicineBatchCreate,
    MedicineBatchUpdate,
    MedicineBatchResponse
)


router = APIRouter(
    prefix="/batches",
    tags=["Medicine Batches"]
)


def validate_references(
    medicine_id: int,
    supplier_id: int | None,
    db: Session
):

    medicine = db.get(Medicine, medicine_id)

    if medicine is None:
        raise HTTPException(
            status_code=404,
            detail="Medicine not found"
        )

    if supplier_id is not None:

        supplier = db.get(Supplier, supplier_id)

        if supplier is None:
            raise HTTPException(
                status_code=404,
                detail="Supplier not found"
            )


# CREATE BATCH
@router.post(
    "/",
    response_model=MedicineBatchResponse,
    status_code=status.HTTP_201_CREATED
)
def create_batch(
    batch_data: MedicineBatchCreate,
    db: Session = Depends(get_db)
):

    validate_references(
        batch_data.medicine_id,
        batch_data.supplier_id,
        db
    )

    batch = MedicineBatch(**batch_data.model_dump())

    try:
        db.add(batch)
        db.commit()
        db.refresh(batch)

        return batch

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Batch already exists or violates a database constraint"
        )


# GET ALL BATCHES
@router.get(
    "/",
    response_model=list[MedicineBatchResponse]
)
def get_all_batches(
    db: Session = Depends(get_db)
):

    statement = select(MedicineBatch).order_by(
        MedicineBatch.batch_id
    )

    return db.execute(statement).scalars().all()


# GET BATCH BY ID
@router.get(
    "/{batch_id}",
    response_model=MedicineBatchResponse
)
def get_batch_by_id(
    batch_id: int,
    db: Session = Depends(get_db)
):

    batch = db.get(MedicineBatch, batch_id)

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    return batch


# UPDATE BATCH
@router.put(
    "/{batch_id}",
    response_model=MedicineBatchResponse
)
def update_batch(
    batch_id: int,
    batch_data: MedicineBatchUpdate,
    db: Session = Depends(get_db)
):

    batch = db.get(MedicineBatch, batch_id)

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    validate_references(
        batch_data.medicine_id,
        batch_data.supplier_id,
        db
    )

    for key, value in batch_data.model_dump().items():
        setattr(batch, key, value)

    try:
        db.commit()
        db.refresh(batch)

        return batch

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Batch update violates a database constraint"
        )


# DELETE BATCH
@router.delete("/{batch_id}")
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db)
):

    batch = db.get(MedicineBatch, batch_id)

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Medicine batch not found"
        )

    inventory_exists = db.execute(
        select(Inventory.inventory_id)
        .where(Inventory.batch_id == batch_id)
        .limit(1)
    ).first()

    transaction_exists = db.execute(
        select(InventoryTransaction.transaction_id)
        .where(InventoryTransaction.batch_id == batch_id)
        .limit(1)
    ).first()

    if inventory_exists or transaction_exists:

        raise HTTPException(
            status_code=409,
            detail="Cannot delete batch because inventory or transaction records reference it"
        )

    db.delete(batch)

    try:
        db.commit()

        return {
            "message": "Medicine batch deleted successfully",
            "batch_id": batch_id
        }

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Cannot delete batch because another record references it"
        )

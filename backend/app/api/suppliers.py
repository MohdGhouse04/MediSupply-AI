
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.database.connection import get_db
from backend.app.models import Supplier, MedicineBatch
from backend.app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse
)


router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"]
)


# CREATE SUPPLIER
@router.post(
    "/",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED
)
def create_supplier(
    supplier_data: SupplierCreate,
    db: Session = Depends(get_db)
):

    supplier = Supplier(**supplier_data.model_dump())

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return supplier


# GET ALL SUPPLIERS
@router.get(
    "/",
    response_model=list[SupplierResponse]
)
def get_all_suppliers(
    db: Session = Depends(get_db)
):

    statement = select(Supplier).order_by(Supplier.supplier_id)

    return db.execute(statement).scalars().all()


# GET SUPPLIER BY ID
@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse
)
def get_supplier_by_id(
    supplier_id: int,
    db: Session = Depends(get_db)
):

    supplier = db.get(Supplier, supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    return supplier


# UPDATE SUPPLIER
@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse
)
def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    db: Session = Depends(get_db)
):

    supplier = db.get(Supplier, supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    for key, value in supplier_data.model_dump().items():
        setattr(supplier, key, value)

    db.commit()
    db.refresh(supplier)

    return supplier


# DELETE SUPPLIER
@router.delete(
    "/{supplier_id}"
)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db)
):

    supplier = db.get(Supplier, supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    # Prevent deletion if medicine batches reference this supplier
    batch_exists = db.execute(
        select(MedicineBatch.batch_id)
        .where(MedicineBatch.supplier_id == supplier_id)
        .limit(1)
    ).first()

    if batch_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete supplier because medicine batches reference it"
        )

    db.delete(supplier)
    db.commit()

    return {
        "message": "Supplier deleted successfully",
        "supplier_id": supplier_id
    }


from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db

from backend.app.models import (
    StockTransfer,
    Facility,
    MedicineBatch,
    Inventory,
    InventoryTransaction
)

from backend.app.schemas.stock_transfer import (
    StockTransferCreate,
    StockTransferResponse,
    StockTransferStatusUpdate
)

router = APIRouter(
    prefix="/stock-transfers",
    tags=["Stock Transfers"]
)


# --------------------------------------------------
# CREATE STOCK TRANSFER REQUEST
# --------------------------------------------------

@router.post(
    "/",
    response_model=StockTransferResponse,
    status_code=201
)
def create_stock_transfer(
    transfer: StockTransferCreate,
    db: Session = Depends(get_db)
):

    try:

        # Validate source facility
        source = db.get(
            Facility,
            transfer.source_facility_id
        )

        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source facility not found"
            )

        # Validate destination facility
        destination = db.get(
            Facility,
            transfer.destination_facility_id
        )

        if not destination:
            raise HTTPException(
                status_code=404,
                detail="Destination facility not found"
            )

        # Source and destination must differ
        if (
            transfer.source_facility_id
            == transfer.destination_facility_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Source and destination facilities must be different"
            )

        # Validate medicine batch
        batch = db.get(
            MedicineBatch,
            transfer.batch_id
        )

        if not batch:
            raise HTTPException(
                status_code=404,
                detail="Medicine batch not found"
            )

        # Batch must be available and not expired
        if batch.batch_status != "AVAILABLE":
            raise HTTPException(
                status_code=400,
                detail="This batch is not available for transfer"
            )

        if batch.expires_on < date.today():
            raise HTTPException(
                status_code=400,
                detail="Expired medicine batches cannot be transferred"
            )

        # Lock source inventory while checking stock
        inventory = db.execute(
            select(Inventory)
            .where(
                Inventory.facility_id
                == transfer.source_facility_id,

                Inventory.batch_id
                == transfer.batch_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        if not inventory:
            raise HTTPException(
                status_code=404,
                detail="Source facility has no inventory record for this batch"
            )

        # Calculate usable stock
        usable_stock = (
            inventory.quantity_on_hand
            - inventory.reserved_quantity
            - inventory.damaged_quantity
        )

        if transfer.quantity > usable_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient usable stock. Available: {usable_stock}"
            )

        # Create transfer request
        new_transfer = StockTransfer(
            source_facility_id=transfer.source_facility_id,
            destination_facility_id=transfer.destination_facility_id,
            batch_id=transfer.batch_id,
            quantity=transfer.quantity,
            status="PENDING",
            remarks=transfer.remarks
        )

        db.add(new_transfer)

        db.commit()

        db.refresh(new_transfer)

        return new_transfer

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# GET STOCK TRANSFER REQUESTS
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[StockTransferResponse]
)
def get_stock_transfers(
    source_facility_id: int | None = Query(
        default=None,
        gt=0
    ),

    destination_facility_id: int | None = Query(
        default=None,
        gt=0
    ),

    batch_id: int | None = Query(
        default=None,
        gt=0
    ),

    status: str | None = None,

    skip: int = Query(
        default=0,
        ge=0
    ),

    limit: int = Query(
        default=100,
        ge=1,
        le=500
    ),

    db: Session = Depends(get_db)
):

    query = select(StockTransfer)

    if source_facility_id is not None:
        query = query.where(
            StockTransfer.source_facility_id
            == source_facility_id
        )

    if destination_facility_id is not None:
        query = query.where(
            StockTransfer.destination_facility_id
            == destination_facility_id
        )

    if batch_id is not None:
        query = query.where(
            StockTransfer.batch_id == batch_id
        )

    if status is not None:

        valid_statuses = [
            "PENDING",
            "APPROVED",
            "DISPATCHED",
            "RECEIVED",
            "REJECTED",
            "CANCELLED"
        ]

        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail="Invalid transfer status"
            )

        query = query.where(
            StockTransfer.status == status
        )

    query = (
        query
        .order_by(StockTransfer.requested_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(query).all()

# --------------------------------------------------
# APPROVE, REJECT OR CANCEL STOCK TRANSFER
# --------------------------------------------------

@router.patch(
    "/{transfer_id}/status",
    response_model=StockTransferResponse
)
def update_stock_transfer_status(
    transfer_id: int,
    update: StockTransferStatusUpdate,
    db: Session = Depends(get_db)
):

    try:

        # Lock transfer record
        transfer = db.execute(
            select(StockTransfer)
            .where(StockTransfer.transfer_id == transfer_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not transfer:
            raise HTTPException(
                status_code=404,
                detail="Stock transfer not found"
            )

        requested_status = update.status

        # Approval and rejection are allowed only from PENDING
        if requested_status in ["APPROVED", "REJECTED"]:

            if transfer.status != "PENDING":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot {requested_status.lower()} a transfer with status {transfer.status}"
                )

        # Cancellation is allowed before dispatch
        elif requested_status == "CANCELLED":

            if transfer.status not in ["PENDING", "APPROVED"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel a transfer with status {transfer.status}"
                )

        # Update status
        transfer.status = requested_status

        if requested_status == "APPROVED":
            transfer.approved_at = datetime.now()

        if update.remarks is not None:
            transfer.remarks = update.remarks

        db.commit()

        db.refresh(transfer)

        return transfer

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

# --------------------------------------------------
# DISPATCH STOCK TRANSFER
# --------------------------------------------------

@router.post(
    "/{transfer_id}/dispatch",
    response_model=StockTransferResponse
)
def dispatch_stock_transfer(
    transfer_id: int,
    db: Session = Depends(get_db)
):

    try:

        # Lock transfer record
        transfer = db.execute(
            select(StockTransfer)
            .where(StockTransfer.transfer_id == transfer_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not transfer:
            raise HTTPException(
                status_code=404,
                detail="Stock transfer not found"
            )

        # Only approved transfers can be dispatched
        if transfer.status != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED transfers can be dispatched. Current status: {transfer.status}"
            )

        # Validate batch again
        batch = db.get(MedicineBatch, transfer.batch_id)

        if not batch:
            raise HTTPException(
                status_code=404,
                detail="Medicine batch not found"
            )

        if batch.batch_status != "AVAILABLE":
            raise HTTPException(
                status_code=400,
                detail="Batch is no longer available for dispatch"
            )

        if batch.expires_on < date.today():
            raise HTTPException(
                status_code=400,
                detail="Expired batch cannot be dispatched"
            )

        # Lock source inventory
        inventory = db.execute(
            select(Inventory)
            .where(
                Inventory.facility_id == transfer.source_facility_id,
                Inventory.batch_id == transfer.batch_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        if not inventory:
            raise HTTPException(
                status_code=404,
                detail="Source inventory record not found"
            )

        # Recalculate usable stock
        usable_stock = (
            inventory.quantity_on_hand
            - inventory.reserved_quantity
            - inventory.damaged_quantity
        )

        if transfer.quantity > usable_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient usable stock at dispatch. Available: {usable_stock}"
            )

        # Deduct stock from source facility
        inventory.quantity_on_hand -= transfer.quantity

        # Record outgoing inventory transaction
        transaction = InventoryTransaction(
            facility_id=transfer.source_facility_id,
            batch_id=transfer.batch_id,
            transaction_type="ISSUED",
            quantity=transfer.quantity,
            reference_number=f"TRANSFER-{transfer.transfer_id}",
            remarks="Stock dispatched to another facility"
        )

        db.add(transaction)

        # Update transfer status
        transfer.status = "DISPATCHED"
        transfer.dispatched_at = datetime.now()

        db.commit()

        db.refresh(transfer)

        return transfer

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

# --------------------------------------------------
# RECEIVE STOCK TRANSFER
# --------------------------------------------------

@router.post(
    "/{transfer_id}/receive",
    response_model=StockTransferResponse
)
def receive_stock_transfer(
    transfer_id: int,
    db: Session = Depends(get_db)
):

    try:

        # Lock transfer record
        transfer = db.execute(
            select(StockTransfer)
            .where(StockTransfer.transfer_id == transfer_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not transfer:
            raise HTTPException(
                status_code=404,
                detail="Stock transfer not found"
            )

        # Only dispatched transfers can be received
        if transfer.status != "DISPATCHED":
            raise HTTPException(
                status_code=400,
                detail=f"Only DISPATCHED transfers can be received. Current status: {transfer.status}"
            )

        # Validate batch
        batch = db.get(MedicineBatch, transfer.batch_id)

        if not batch:
            raise HTTPException(
                status_code=404,
                detail="Medicine batch not found"
            )

        if batch.batch_status != "AVAILABLE":
            raise HTTPException(
                status_code=400,
                detail="Cannot receive stock because the batch is no longer available"
            )

        if batch.expires_on < date.today():
            raise HTTPException(
                status_code=400,
                detail="Cannot receive an expired medicine batch"
            )

        # Lock destination inventory
        inventory = db.execute(
            select(Inventory)
            .where(
                Inventory.facility_id == transfer.destination_facility_id,
                Inventory.batch_id == transfer.batch_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        # Create inventory record if it does not exist
        if not inventory:

            inventory = Inventory(
                facility_id=transfer.destination_facility_id,
                batch_id=transfer.batch_id,
                quantity_on_hand=0,
                reserved_quantity=0,
                damaged_quantity=0
            )

            db.add(inventory)
            db.flush()

        # Add received stock
        inventory.quantity_on_hand += transfer.quantity

        # Record incoming inventory transaction
        transaction = InventoryTransaction(
            facility_id=transfer.destination_facility_id,
            batch_id=transfer.batch_id,
            transaction_type="RECEIVED",
            quantity=transfer.quantity,
            reference_number=f"TRANSFER-{transfer.transfer_id}",
            remarks="Stock received from another facility"
        )

        db.add(transaction)

        # Update transfer status
        transfer.status = "RECEIVED"
        transfer.received_at = datetime.now()

        db.commit()

        db.refresh(transfer)

        return transfer

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

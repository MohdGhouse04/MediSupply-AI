
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db

from backend.app.models import (
    Inventory,
    Facility,
    MedicineBatch,
    InventoryTransaction
)

from backend.app.schemas.inventory_transaction import (
    InventoryTransactionCreate,
    InventoryTransactionResponse
)

from backend.app.services.outbox_service import add_outbox_event


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transactions",
    tags=["Inventory Transactions"]
)


# =========================================================
# POST: CREATE INVENTORY TRANSACTION + TRANSACTIONAL OUTBOX
# =========================================================

@router.post(
    "/",
    response_model=InventoryTransactionResponse,
    status_code=201
)
def create_inventory_transaction(
    transaction: InventoryTransactionCreate,
    db: Session = Depends(get_db)
):

    try:

        # 1. Check facility
        facility = db.get(Facility, transaction.facility_id)

        if not facility:
            raise HTTPException(
                status_code=404,
                detail="Facility not found"
            )

        # 2. Check medicine batch
        batch = db.get(MedicineBatch, transaction.batch_id)

        if not batch:
            raise HTTPException(
                status_code=404,
                detail="Medicine batch not found"
            )

        # 3. Lock inventory record
        inventory = db.execute(
            select(Inventory)
            .where(
                Inventory.facility_id == transaction.facility_id,
                Inventory.batch_id == transaction.batch_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        # 4. Create inventory if missing
        if not inventory:

            if transaction.transaction_type != "RECEIVED":
                raise HTTPException(
                    status_code=404,
                    detail="Inventory record not found for this facility and batch"
                )

            inventory = Inventory(
                facility_id=transaction.facility_id,
                batch_id=transaction.batch_id,
                quantity_on_hand=0,
                reserved_quantity=0,
                damaged_quantity=0
            )

            db.add(inventory)
            db.flush()

        # 5. Calculate usable stock
        usable_stock = (
            inventory.quantity_on_hand
            - inventory.reserved_quantity
            - inventory.damaged_quantity
        )

        # 6. Process transaction types

        if transaction.transaction_type == "RECEIVED":

            if (
                batch.batch_status != "AVAILABLE"
                or batch.expires_on < date.today()
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot receive stock into an expired or unavailable batch"
                )

            inventory.quantity_on_hand += transaction.quantity

        elif transaction.transaction_type == "ISSUED":

            if transaction.quantity > usable_stock:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient usable stock"
                )

            inventory.quantity_on_hand -= transaction.quantity

        elif transaction.transaction_type == "DAMAGED":

            if transaction.quantity > usable_stock:
                raise HTTPException(
                    status_code=400,
                    detail="Damaged quantity exceeds usable stock"
                )

            inventory.damaged_quantity += transaction.quantity

        elif transaction.transaction_type == "ADJUSTMENT":

            if transaction.adjustment_direction == "INCREASE":

                if (
                    batch.batch_status != "AVAILABLE"
                    or batch.expires_on < date.today()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot increase stock for an expired or unavailable batch"
                    )

                inventory.quantity_on_hand += transaction.quantity

            elif transaction.adjustment_direction == "DECREASE":

                if transaction.quantity > usable_stock:
                    raise HTTPException(
                        status_code=400,
                        detail="Adjustment quantity exceeds usable stock"
                    )

                inventory.quantity_on_hand -= transaction.quantity

        # 7. Save transaction history
        new_transaction = InventoryTransaction(
            facility_id=transaction.facility_id,
            batch_id=transaction.batch_id,
            transaction_type=transaction.transaction_type,
            quantity=transaction.quantity,
            adjustment_direction=transaction.adjustment_direction,
            reference_number=transaction.reference_number,
            remarks=transaction.remarks
        )

        db.add(new_transaction)

        # Flush to generate transaction ID before creating the event
        db.flush()

        # 8. Build inventory event
        event = {
            "event_id": str(new_transaction.transaction_id),
            "event_type": f"INVENTORY_{transaction.transaction_type}",
            "transaction_id": new_transaction.transaction_id,
            "facility_id": transaction.facility_id,
            "medicine_id": batch.medicine_id,
            "batch_id": transaction.batch_id,
            "transaction_type": transaction.transaction_type,
            "quantity": transaction.quantity,
            "adjustment_direction": transaction.adjustment_direction,
            "reference_number": transaction.reference_number,
            "transaction_date": (
                new_transaction.transaction_date.isoformat()
                if new_transaction.transaction_date
                else None
            )
        }

        # 9. Save event to transactional outbox
        add_outbox_event(
            db=db,
            event=event,
            topic="inventory-events"
        )

        # 10. Commit business data and outbox event together
        db.commit()

        db.refresh(new_transaction)

        logger.info(
            "Inventory transaction %s and outbox event committed successfully",
            new_transaction.transaction_id
        )

        return new_transaction

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        logger.exception("Inventory transaction creation failed")
        raise


# =========================================================
# GET: INVENTORY TRANSACTION HISTORY
# =========================================================

@router.get(
    "/",
    response_model=list[InventoryTransactionResponse]
)
def get_inventory_transactions(
    facility_id: int | None = Query(default=None, gt=0),
    batch_id: int | None = Query(default=None, gt=0),
    transaction_type: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):

    statement = select(InventoryTransaction)

    if facility_id is not None:
        statement = statement.where(
            InventoryTransaction.facility_id == facility_id
        )

    if batch_id is not None:
        statement = statement.where(
            InventoryTransaction.batch_id == batch_id
        )

    if transaction_type is not None:
        statement = statement.where(
            InventoryTransaction.transaction_type == transaction_type.upper()
        )

    statement = (
        statement
        .order_by(InventoryTransaction.transaction_date.desc())
        .offset(skip)
        .limit(limit)
    )

    return db.execute(statement).scalars().all()


# =========================================================
# GET: INVENTORY TRANSACTION SUMMARY
# =========================================================

@router.get("/summary")
def get_inventory_transaction_summary(
    facility_id: int | None = Query(default=None, gt=0),
    batch_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db)
):

    statement = select(
        InventoryTransaction.transaction_type,
        func.count(InventoryTransaction.transaction_id).label(
            "total_transactions"
        ),
        func.sum(InventoryTransaction.quantity).label(
            "total_quantity"
        )
    )

    if facility_id is not None:
        statement = statement.where(
            InventoryTransaction.facility_id == facility_id
        )

    if batch_id is not None:
        statement = statement.where(
            InventoryTransaction.batch_id == batch_id
        )

    statement = statement.group_by(
        InventoryTransaction.transaction_type
    )

    results = db.execute(statement).mappings().all()

    return {
        "total_transaction_types": len(results),
        "summary": [
            dict(row)
            for row in results
        ]
    }


# =========================================================
# GET: TRANSACTION COUNTS BY FACILITY
# =========================================================

@router.get("/summary/facilities")
def get_transaction_summary_by_facility(
    db: Session = Depends(get_db)
):

    statement = (
        select(
            Facility.facility_id,
            Facility.facility_name,
            func.count(
                InventoryTransaction.transaction_id
            ).label("total_transactions"),
            func.sum(
                InventoryTransaction.quantity
            ).label("total_quantity")
        )
        .join(
            InventoryTransaction,
            InventoryTransaction.facility_id == Facility.facility_id
        )
        .group_by(
            Facility.facility_id,
            Facility.facility_name
        )
        .order_by(Facility.facility_id)
    )

    results = db.execute(statement).mappings().all()

    return [
        dict(row)
        for row in results
    ]

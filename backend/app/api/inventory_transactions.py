
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


router = APIRouter(
    prefix="/transactions",
    tags=["Inventory Transactions"]
)


# =========================================================
# POST: CREATE INVENTORY TRANSACTION
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

        # 1. Check whether facility exists
        facility = db.get(Facility, transaction.facility_id)

        if not facility:
            raise HTTPException(
                status_code=404,
                detail="Facility not found"
            )

        # 2. Check whether medicine batch exists
        batch = db.get(MedicineBatch, transaction.batch_id)

        if not batch:
            raise HTTPException(
                status_code=404,
                detail="Medicine batch not found"
            )

        # 3. Find inventory record and lock it
        inventory = db.execute(
            select(Inventory)
            .where(
                Inventory.facility_id == transaction.facility_id,
                Inventory.batch_id == transaction.batch_id
            )
            .with_for_update()
        ).scalar_one_or_none()

        # 4. Create inventory record if it does not exist
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

        # =================================================
        # 6. PROCESS TRANSACTION TYPES
        # =================================================

        # RECEIVED
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

        # ISSUED
        elif transaction.transaction_type == "ISSUED":

            if transaction.quantity > usable_stock:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient usable stock"
                )

            inventory.quantity_on_hand -= transaction.quantity

        # DAMAGED
        elif transaction.transaction_type == "DAMAGED":

            if transaction.quantity > usable_stock:
                raise HTTPException(
                    status_code=400,
                    detail="Damaged quantity exceeds usable stock"
                )

            inventory.damaged_quantity += transaction.quantity

        # ADJUSTMENT
        elif transaction.transaction_type == "ADJUSTMENT":

            # INCREASE STOCK
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

            # DECREASE STOCK
            elif transaction.adjustment_direction == "DECREASE":

                if transaction.quantity > usable_stock:
                    raise HTTPException(
                        status_code=400,
                        detail="Adjustment quantity exceeds usable stock"
                    )

                inventory.quantity_on_hand -= transaction.quantity

        # =================================================
        # 7. SAVE TRANSACTION HISTORY
        # =================================================

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

        # 8. Commit changes
        db.commit()

        db.refresh(new_transaction)

        return new_transaction

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
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
    transaction_type: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):

    query = select(InventoryTransaction)

    # Filter by facility
    if facility_id is not None:

        query = query.where(
            InventoryTransaction.facility_id == facility_id
        )

    # Filter by batch
    if batch_id is not None:

        query = query.where(
            InventoryTransaction.batch_id == batch_id
        )

    # Filter by transaction type
    if transaction_type is not None:

        valid_types = [
            "RECEIVED",
            "ISSUED",
            "DAMAGED",
            "ADJUSTMENT"
        ]

        if transaction_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail="Invalid transaction type"
            )

        query = query.where(
            InventoryTransaction.transaction_type == transaction_type
        )

    # Sorting and pagination
    query = (
        query
        .order_by(
            InventoryTransaction.transaction_date.desc()
        )
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(query).all()

# =========================================================
# GET: INVENTORY TRANSACTION SUMMARY
# =========================================================

@router.get("/summary")
def get_transaction_summary(
    facility_id: int | None = Query(default=None, gt=0),
    batch_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db)
):

    query = select(
        func.coalesce(
            func.sum(
                case(
                    (
                        InventoryTransaction.transaction_type == "RECEIVED",
                        InventoryTransaction.quantity
                    ),
                    else_=0
                )
            ), 0
        ).label("total_received"),

        func.coalesce(
            func.sum(
                case(
                    (
                        InventoryTransaction.transaction_type == "ISSUED",
                        InventoryTransaction.quantity
                    ),
                    else_=0
                )
            ), 0
        ).label("total_issued"),

        func.coalesce(
            func.sum(
                case(
                    (
                        InventoryTransaction.transaction_type == "DAMAGED",
                        InventoryTransaction.quantity
                    ),
                    else_=0
                )
            ), 0
        ).label("total_damaged"),

        func.coalesce(
            func.sum(
                case(
                    (
                        InventoryTransaction.adjustment_direction == "INCREASE",
                        InventoryTransaction.quantity
                    ),
                    else_=0
                )
            ), 0
        ).label("adjustment_increase"),

        func.coalesce(
            func.sum(
                case(
                    (
                        InventoryTransaction.adjustment_direction == "DECREASE",
                        InventoryTransaction.quantity
                    ),
                    else_=0
                )
            ), 0
        ).label("adjustment_decrease")
    )

    if facility_id is not None:
        query = query.where(
            InventoryTransaction.facility_id == facility_id
        )

    if batch_id is not None:
        query = query.where(
            InventoryTransaction.batch_id == batch_id
        )

    result = db.execute(query).one()

    total_received = int(result.total_received)
    total_issued = int(result.total_issued)
    total_damaged = int(result.total_damaged)
    adjustment_increase = int(result.adjustment_increase)
    adjustment_decrease = int(result.adjustment_decrease)

    net_usable_stock_movement = (
        total_received
        - total_issued
        - total_damaged
        + adjustment_increase
        - adjustment_decrease
    )

    return {
        "facility_id": facility_id,
        "batch_id": batch_id,
        "total_received": total_received,
        "total_issued": total_issued,
        "total_damaged": total_damaged,
        "adjustment_increase": adjustment_increase,
        "adjustment_decrease": adjustment_decrease,
        "net_usable_stock_movement": net_usable_stock_movement
    }

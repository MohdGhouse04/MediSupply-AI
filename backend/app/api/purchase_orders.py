
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db

from backend.app.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    Facility,
    Supplier,
    Medicine
)

from backend.app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderStatusUpdate
)


router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"]
)


# --------------------------------------------------
# CREATE PURCHASE ORDER
# --------------------------------------------------

@router.post("/", status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db)
):

    facility = db.get(Facility, payload.facility_id)

    if facility is None:
        raise HTTPException(
            status_code=404,
            detail="Facility not found"
        )

    supplier = db.get(Supplier, payload.supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    medicine_ids = [
        item.medicine_id for item in payload.items
    ]

    medicines = (
        db.query(Medicine)
        .filter(Medicine.medicine_id.in_(medicine_ids))
        .all()
    )

    found_ids = {
        medicine.medicine_id for medicine in medicines
    }

    missing_ids = set(medicine_ids) - found_ids

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Medicines not found: {sorted(missing_ids)}"
        )

    total_amount = sum(
        (
            item.unit_cost * item.ordered_quantity
            for item in payload.items
        ),
        Decimal("0.00")
    )

    try:

        purchase_order = PurchaseOrder(
            facility_id=payload.facility_id,
            supplier_id=payload.supplier_id,
            status="DRAFT",
            expected_delivery_date=payload.expected_delivery_date,
            total_amount=total_amount,
            remarks=payload.remarks
        )

        db.add(purchase_order)
        db.flush()

        for item in payload.items:

            order_item = PurchaseOrderItem(
                purchase_order_id=purchase_order.purchase_order_id,
                medicine_id=item.medicine_id,
                ordered_quantity=item.ordered_quantity,
                received_quantity=0,
                unit_cost=item.unit_cost
            )

            db.add(order_item)

        db.commit()
        db.refresh(purchase_order)

        return {
            "message": "Purchase order created successfully",
            "purchase_order_id": purchase_order.purchase_order_id,
            "status": purchase_order.status,
            "total_amount": purchase_order.total_amount
        }

    except Exception:

        db.rollback()
        raise


# --------------------------------------------------
# LIST PURCHASE ORDERS
# --------------------------------------------------

@router.get("/")
def list_purchase_orders(
    facility_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db)
):

    query = db.query(PurchaseOrder)

    if facility_id is not None:
        query = query.filter(
            PurchaseOrder.facility_id == facility_id
        )

    if supplier_id is not None:
        query = query.filter(
            PurchaseOrder.supplier_id == supplier_id
        )

    if status is not None:
        query = query.filter(
            PurchaseOrder.status == status.upper()
        )

    return (
        query
        .order_by(PurchaseOrder.purchase_order_id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# --------------------------------------------------
# GET PURCHASE ORDER DETAILS
# --------------------------------------------------

@router.get("/{purchase_order_id}")
def get_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db)
):

    purchase_order = db.get(
        PurchaseOrder,
        purchase_order_id
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    items = (
        db.query(PurchaseOrderItem)
        .filter(
            PurchaseOrderItem.purchase_order_id
            == purchase_order_id
        )
        .all()
    )

    return {
        "purchase_order": purchase_order,
        "items": items
    }


# --------------------------------------------------
# UPDATE PURCHASE ORDER STATUS
# --------------------------------------------------

@router.patch("/{purchase_order_id}/status")
def update_purchase_order_status(
    purchase_order_id: int,
    payload: PurchaseOrderStatusUpdate,
    db: Session = Depends(get_db)
):

    purchase_order = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.purchase_order_id
            == purchase_order_id
        )
        .with_for_update()
        .first()
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    current_status = purchase_order.status
    new_status = payload.status

    allowed_transitions = {
        "DRAFT": ["PENDING_APPROVAL", "CANCELLED"],
        "PENDING_APPROVAL": ["APPROVED", "REJECTED", "CANCELLED"],
        "APPROVED": ["ORDERED", "CANCELLED"],
        "REJECTED": [],
        "ORDERED": [],
        "PARTIALLY_RECEIVED": [],
        "RECEIVED": [],
        "CANCELLED": []
    }

    if new_status not in allowed_transitions.get(
        current_status,
        []
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot change purchase order from "
                f"{current_status} to {new_status}"
            )
        )

    now = datetime.now()

    purchase_order.status = new_status

    if new_status == "APPROVED":
        purchase_order.approved_at = now

    if new_status == "ORDERED":
        purchase_order.ordered_at = now

    if payload.remarks is not None:
        purchase_order.remarks = payload.remarks

    try:

        db.commit()
        db.refresh(purchase_order)

        return {
            "message": "Purchase order status updated",
            "purchase_order_id": purchase_order_id,
            "old_status": current_status,
            "new_status": purchase_order.status
        }

    except Exception:

        db.rollback()
        raise

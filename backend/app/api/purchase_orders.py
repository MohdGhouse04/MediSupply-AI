
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db

from backend.app.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    Facility,
    Supplier,
    Medicine,
    MedicineBatch,
    Inventory,
    InventoryTransaction
)

from backend.app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderStatusUpdate,
    PurchaseOrderReceive
)

from backend.app.services.outbox_service import add_outbox_event


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

        event = {
            "event_id": f"PO-{purchase_order.purchase_order_id}-CREATED",
            "event_type": "PURCHASE_ORDER_CREATED",
            "purchase_order_id": purchase_order.purchase_order_id,
            "facility_id": purchase_order.facility_id,
            "supplier_id": purchase_order.supplier_id,
            "status": purchase_order.status,
            "total_amount": str(purchase_order.total_amount),
            "expected_delivery_date": (
                str(purchase_order.expected_delivery_date)
                if purchase_order.expected_delivery_date
                else None
            ),
            "event_timestamp": datetime.now().isoformat()
        }

        add_outbox_event(
            db,
            event,
            topic="purchase-order-events"
        )

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

        event = {
            "event_id": (
                f"PO-{purchase_order_id}-STATUS-{new_status}"
            ),
            "event_type": f"PURCHASE_ORDER_{new_status}",
            "purchase_order_id": purchase_order_id,
            "facility_id": purchase_order.facility_id,
            "supplier_id": purchase_order.supplier_id,
            "old_status": current_status,
            "new_status": new_status,
            "event_timestamp": datetime.now().isoformat()
        }

        add_outbox_event(
            db,
            event,
            topic="purchase-order-events"
        )

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


# --------------------------------------------------
# RECEIVE PURCHASE ORDER GOODS
# --------------------------------------------------

@router.post("/{purchase_order_id}/receive")
def receive_purchase_order(
    purchase_order_id: int,
    payload: PurchaseOrderReceive,
    db: Session = Depends(get_db)
):

    try:

        purchase_order = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.purchase_order_id == purchase_order_id
            )
            .with_for_update()
            .first()
        )

        if purchase_order is None:
            raise HTTPException(
                status_code=404,
                detail="Purchase order not found"
            )

        if purchase_order.status not in [
            "ORDERED",
            "PARTIALLY_RECEIVED"
        ]:
            raise HTTPException(
                status_code=409,
                detail="Goods can only be received for ordered purchase orders"
            )

        received_summary = []

        for receipt_item in payload.items:

            order_item = (
                db.query(PurchaseOrderItem)
                .filter(
                    PurchaseOrderItem.purchase_order_item_id
                    == receipt_item.purchase_order_item_id,
                    PurchaseOrderItem.purchase_order_id
                    == purchase_order_id
                )
                .with_for_update()
                .first()
            )

            if order_item is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Purchase order item "
                        f"{receipt_item.purchase_order_item_id} not found"
                    )
                )

            outstanding_quantity = (
                order_item.ordered_quantity
                - order_item.received_quantity
            )

            if receipt_item.received_quantity > outstanding_quantity:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Received quantity exceeds outstanding quantity "
                        f"for medicine {order_item.medicine_id}. "
                        f"Outstanding: {outstanding_quantity}"
                    )
                )

            if receipt_item.expires_on <= date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Cannot receive an already expired batch"
                )

            batch = (
                db.query(MedicineBatch)
                .filter(
                    MedicineBatch.medicine_id == order_item.medicine_id,
                    MedicineBatch.supplier_id == purchase_order.supplier_id,
                    MedicineBatch.batch_number == receipt_item.batch_number
                )
                .with_for_update()
                .first()
            )

            if batch is None:

                batch = MedicineBatch(
                    medicine_id=order_item.medicine_id,
                    supplier_id=purchase_order.supplier_id,
                    batch_number=receipt_item.batch_number,
                    manufactured_on=receipt_item.manufactured_on,
                    expires_on=receipt_item.expires_on,
                    received_quantity=receipt_item.received_quantity,
                    unit_cost=order_item.unit_cost,
                    batch_status="AVAILABLE"
                )

                db.add(batch)
                db.flush()

            else:

                if batch.batch_status != "AVAILABLE":
                    raise HTTPException(
                        status_code=409,
                        detail="Cannot receive stock into a quarantined or recalled batch"
                    )

                if (
                    batch.manufactured_on != receipt_item.manufactured_on
                    or batch.expires_on != receipt_item.expires_on
                    or batch.unit_cost != order_item.unit_cost
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Existing batch metadata does not match the delivery"
                    )

                batch.received_quantity += receipt_item.received_quantity

            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.facility_id == purchase_order.facility_id,
                    Inventory.batch_id == batch.batch_id
                )
                .with_for_update()
                .first()
            )

            if inventory is None:

                inventory = Inventory(
                    facility_id=purchase_order.facility_id,
                    batch_id=batch.batch_id,
                    quantity_on_hand=receipt_item.received_quantity,
                    reserved_quantity=0,
                    damaged_quantity=0
                )

                db.add(inventory)

            else:

                inventory.quantity_on_hand += receipt_item.received_quantity

            transaction = InventoryTransaction(
                facility_id=purchase_order.facility_id,
                batch_id=batch.batch_id,
                transaction_type="RECEIVED",
                quantity=receipt_item.received_quantity,
                reference_number=f"PO-{purchase_order_id}",
                remarks=(
                    receipt_item.remarks
                    or payload.remarks
                    or f"Goods received against PO-{purchase_order_id}"
                )
            )

            db.add(transaction)

            order_item.received_quantity += receipt_item.received_quantity

            received_summary.append({
                "purchase_order_item_id": order_item.purchase_order_item_id,
                "medicine_id": order_item.medicine_id,
                "batch_id": batch.batch_id,
                "batch_number": batch.batch_number,
                "received_quantity": receipt_item.received_quantity,
                "total_received_quantity": order_item.received_quantity,
                "outstanding_quantity": (
                    order_item.ordered_quantity
                    - order_item.received_quantity
                )
            })

        all_items = (
            db.query(PurchaseOrderItem)
            .filter(
                PurchaseOrderItem.purchase_order_id == purchase_order_id
            )
            .with_for_update()
            .all()
        )

        all_received = all(
            item.received_quantity == item.ordered_quantity
            for item in all_items
        )

        if all_received:
            purchase_order.status = "RECEIVED"
            purchase_order.received_at = datetime.now()
        else:
            purchase_order.status = "PARTIALLY_RECEIVED"

        final_status = purchase_order.status

        event = {
            "event_id": (
                f"PO-{purchase_order_id}-RECEIPT-"
                f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            ),
            "event_type": (
                "PURCHASE_ORDER_RECEIVED"
                if final_status == "RECEIVED"
                else "PURCHASE_ORDER_PARTIALLY_RECEIVED"
            ),
            "purchase_order_id": purchase_order_id,
            "facility_id": purchase_order.facility_id,
            "supplier_id": purchase_order.supplier_id,
            "purchase_order_status": final_status,
            "received_items": received_summary,
            "event_timestamp": datetime.now().isoformat()
        }

        add_outbox_event(
            db,
            event,
            topic="purchase-order-events"
        )

        db.commit()

        return {
            "message": "Goods received successfully",
            "purchase_order_id": purchase_order_id,
            "purchase_order_status": final_status,
            "received_items": received_summary
        }

    except Exception:
        db.rollback()
        raise

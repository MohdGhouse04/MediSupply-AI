from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderStatusUpdate,
    PurchaseOrderReceive,
)


def valid_order():
    return {
        "facility_id": 1,
        "supplier_id": 2,
        "items": [
            {
                "medicine_id": 10,
                "ordered_quantity": 100,
                "unit_cost": "5.50",
            }
        ],
    }


def valid_receipt():
    return {
        "items": [
            {
                "purchase_order_item_id": 1,
                "received_quantity": 40,
                "batch_number": "BATCH-001",
                "manufactured_on": date.today(),
                "expires_on": date.today() + timedelta(days=365),
            }
        ]
    }


def test_valid_purchase_order_schema():
    order = PurchaseOrderCreate(**valid_order())

    assert order.facility_id == 1
    assert order.supplier_id == 2
    assert order.items[0].unit_cost == Decimal("5.50")


def test_purchase_order_rejects_duplicate_medicines():
    data = valid_order()
    data["items"].append(data["items"][0].copy())

    with pytest.raises(ValidationError, match="only once"):
        PurchaseOrderCreate(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("facility_id", 0),
        ("supplier_id", -1),
    ],
)
def test_purchase_order_rejects_invalid_ids(field, value):
    data = valid_order()
    data[field] = value

    with pytest.raises(ValidationError):
        PurchaseOrderCreate(**data)


def test_purchase_order_rejects_empty_items():
    data = valid_order()
    data["items"] = []

    with pytest.raises(ValidationError):
        PurchaseOrderCreate(**data)


def test_purchase_order_rejects_nonpositive_quantity():
    data = valid_order()
    data["items"][0]["ordered_quantity"] = 0

    with pytest.raises(ValidationError):
        PurchaseOrderCreate(**data)


def test_purchase_order_rejects_negative_unit_cost():
    data = valid_order()
    data["items"][0]["unit_cost"] = "-1"

    with pytest.raises(ValidationError):
        PurchaseOrderCreate(**data)


def test_status_update_rejects_unsupported_status():
    with pytest.raises(ValidationError):
        PurchaseOrderStatusUpdate(status="RECEIVED")


def test_valid_receipt_schema():
    receipt = PurchaseOrderReceive(**valid_receipt())

    assert receipt.items[0].received_quantity == 40
    assert receipt.items[0].batch_number == "BATCH-001"


def test_receipt_rejects_duplicate_order_items():
    data = valid_receipt()
    data["items"].append(data["items"][0].copy())

    with pytest.raises(ValidationError, match="only once"):
        PurchaseOrderReceive(**data)


def test_receipt_rejects_expiry_before_manufacturing():
    data = valid_receipt()
    data["items"][0]["expires_on"] = date.today() - timedelta(days=1)

    with pytest.raises(ValidationError, match="Expiry date"):
        PurchaseOrderReceive(**data)


def test_receipt_rejects_expiry_equal_to_manufacturing():
    data = valid_receipt()
    data["items"][0]["expires_on"] = data["items"][0]["manufactured_on"]

    with pytest.raises(ValidationError, match="Expiry date"):
        PurchaseOrderReceive(**data)


def test_receipt_rejects_zero_received_quantity():
    data = valid_receipt()
    data["items"][0]["received_quantity"] = 0

    with pytest.raises(ValidationError):
        PurchaseOrderReceive(**data)

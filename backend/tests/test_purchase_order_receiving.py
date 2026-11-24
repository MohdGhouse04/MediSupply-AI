from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db
from backend.app.api import purchase_orders
from backend.app.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    MedicineBatch,
    Inventory,
)


def make_order(status="ORDERED"):
    return SimpleNamespace(
        purchase_order_id=1,
        facility_id=10,
        supplier_id=20,
        status=status,
        received_at=None,
    )


def make_item(ordered=100, received=0):
    return SimpleNamespace(
        purchase_order_item_id=5,
        purchase_order_id=1,
        medicine_id=30,
        ordered_quantity=ordered,
        received_quantity=received,
        unit_cost=Decimal("5.00"),
    )


def make_batch(status="AVAILABLE"):
    return SimpleNamespace(
        batch_id=50,
        medicine_id=30,
        supplier_id=20,
        batch_number="BATCH-001",
        manufactured_on=date.today() - timedelta(days=30),
        expires_on=date.today() + timedelta(days=365),
        received_quantity=100,
        unit_cost=Decimal("5.00"),
        batch_status=status,
    )


def make_inventory(quantity=20):
    return SimpleNamespace(
        inventory_id=60,
        facility_id=10,
        batch_id=50,
        quantity_on_hand=quantity,
        reserved_quantity=0,
        damaged_quantity=0,
    )


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        if self.model is PurchaseOrder:
            return self.db.order
        if self.model is PurchaseOrderItem:
            return self.db.item
        if self.model is MedicineBatch:
            return self.db.batch
        if self.model is Inventory:
            return self.db.inventory
        return None

    def all(self):
        if self.model is PurchaseOrderItem:
            return self.db.all_items
        return []


class FakeDB:
    def __init__(
        self,
        order=None,
        item=None,
        batch=None,
        inventory=None,
    ):
        self.order = order
        self.item = item
        self.batch = batch
        self.inventory = inventory
        self.all_items = [item] if item else []
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, instance):
        self.added.append(instance)

    def flush(self):
        for instance in self.added:
            if isinstance(instance, MedicineBatch) and instance.batch_id is None:
                instance.batch_id = 51
                self.batch = instance

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def receive_payload(quantity=40, expires_on=None):
    return {
        "items": [
            {
                "purchase_order_item_id": 5,
                "received_quantity": quantity,
                "batch_number": "BATCH-001",
                "manufactured_on": (
                    date.today() - timedelta(days=30)
                ).isoformat(),
                "expires_on": (
                    expires_on or date.today() + timedelta(days=365)
                ).isoformat(),
            }
        ]
    }


def call_receive(monkeypatch, db, payload, outbox_handler=None):
    monkeypatch.setattr(
        purchase_orders,
        "add_outbox_event",
        outbox_handler or (lambda *args, **kwargs: None),
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            return client.post(
                "/purchase-orders/1/receive",
                json=payload,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_receiving_rejects_non_ordered_purchase_order(monkeypatch):
    db = FakeDB(order=make_order("APPROVED"))

    response = call_receive(
        monkeypatch, db, receive_payload()
    )

    assert response.status_code == 409
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rejects_missing_purchase_order(monkeypatch):
    db = FakeDB(order=None)

    response = call_receive(
        monkeypatch, db, receive_payload()
    )

    assert response.status_code == 404
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rejects_missing_order_item(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=None,
    )

    response = call_receive(
        monkeypatch, db, receive_payload()
    )

    assert response.status_code == 404
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rejects_quantity_above_outstanding(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(ordered=100, received=80),
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=30)
    )

    assert response.status_code == 400
    assert "exceeds outstanding quantity" in response.json()["detail"]
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rejects_expired_batch(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(),
    )

    response = call_receive(
        monkeypatch,
        db,
        receive_payload(
            expires_on=date.today()
        ),
    )

    assert response.status_code == 400
    assert "expired batch" in response.json()["detail"]
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rejects_quarantined_batch(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(),
        batch=make_batch("QUARANTINED"),
    )

    response = call_receive(
        monkeypatch, db, receive_payload()
    )

    assert response.status_code == 409
    assert "quarantined or recalled" in response.json()["detail"]
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_successful_partial_receipt_updates_inventory(monkeypatch):
    order = make_order()
    item = make_item()
    batch = make_batch()
    inventory = make_inventory()

    db = FakeDB(
        order=order,
        item=item,
        batch=batch,
        inventory=inventory,
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=40)
    )

    assert response.status_code == 200
    assert response.json()["purchase_order_status"] == "PARTIALLY_RECEIVED"

    assert item.received_quantity == 40
    assert batch.received_quantity == 140
    assert inventory.quantity_on_hand == 60

    assert any(
        getattr(entry, "transaction_type", None) == "RECEIVED"
        and entry.quantity == 40
        for entry in db.added
    )

    assert db.commit_count == 1
    assert db.rollback_count == 0


def test_receiving_creates_new_batch(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(),
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=40)
    )

    assert response.status_code == 200
    assert db.batch is not None
    assert db.batch.batch_id == 51
    assert db.batch.batch_number == "BATCH-001"
    assert db.batch.received_quantity == 40
    assert db.batch.batch_status == "AVAILABLE"
    assert db.commit_count == 1


def test_receiving_creates_missing_inventory(monkeypatch):
    batch = make_batch()
    db = FakeDB(
        order=make_order(),
        item=make_item(),
        batch=batch,
        inventory=None,
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=40)
    )

    assert response.status_code == 200

    created_inventory = next(
        entry for entry in db.added
        if isinstance(entry, Inventory)
    )

    assert created_inventory.facility_id == 10
    assert created_inventory.batch_id == 50
    assert created_inventory.quantity_on_hand == 40
    assert created_inventory.reserved_quantity == 0
    assert created_inventory.damaged_quantity == 0


def test_receiving_completes_purchase_order(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(ordered=40),
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=40)
    )

    assert response.status_code == 200
    assert response.json()["purchase_order_status"] == "RECEIVED"
    assert db.order.status == "RECEIVED"
    assert db.order.received_at is not None
    assert db.item.received_quantity == 40
    assert db.commit_count == 1


def test_receiving_rejects_batch_metadata_mismatch(monkeypatch):
    batch = make_batch()
    batch.expires_on = date.today() + timedelta(days=180)

    db = FakeDB(
        order=make_order(),
        item=make_item(),
        batch=batch,
        inventory=make_inventory(),
    )

    response = call_receive(
        monkeypatch, db, receive_payload(quantity=40)
    )

    assert response.status_code == 409
    assert "metadata does not match" in response.json()["detail"]
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_receiving_rolls_back_when_outbox_event_fails(monkeypatch):
    db = FakeDB(
        order=make_order(),
        item=make_item(),
        batch=make_batch(),
        inventory=make_inventory(),
    )

    def fail_outbox(*args, **kwargs):
        raise RuntimeError("Outbox unavailable")

    with pytest.raises(RuntimeError, match="Outbox unavailable"):
        call_receive(
            monkeypatch,
            db,
            receive_payload(quantity=40),
            outbox_handler=fail_outbox,
        )

    assert db.commit_count == 0
    assert db.rollback_count == 1

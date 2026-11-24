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
    Facility,
    Supplier,
    Medicine,
)


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        if self.model is Medicine:
            return self.db.medicines
        return []


class FakeDB:
    def __init__(
        self,
        facility=True,
        supplier=True,
        medicines=None,
    ):
        self.facility = SimpleNamespace(facility_id=10) if facility else None
        self.supplier = SimpleNamespace(supplier_id=20) if supplier else None
        self.medicines = [
            SimpleNamespace(medicine_id=medicine_id)
            for medicine_id in (medicines or [30, 31])
        ]

        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0
        self.next_order_id = 100

    def get(self, model, record_id):
        if model is Facility:
            return self.facility
        if model is Supplier:
            return self.supplier
        return None

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, instance):
        self.added.append(instance)

    def flush(self):
        for instance in self.added:
            if isinstance(instance, PurchaseOrder):
                instance.purchase_order_id = self.next_order_id

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, instance):
        self.refresh_count += 1


def create_payload():
    return {
        "facility_id": 10,
        "supplier_id": 20,
        "expected_delivery_date": "2026-12-15T10:00:00",
        "remarks": "Urgent replenishment",
        "items": [
            {
                "medicine_id": 30,
                "ordered_quantity": 10,
                "unit_cost": "12.50",
            },
            {
                "medicine_id": 31,
                "ordered_quantity": 4,
                "unit_cost": "25.00",
            },
        ],
    }


def call_create(monkeypatch, db, outbox_handler=None):
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
                "/purchase-orders/",
                json=create_payload(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_creation_rejects_missing_facility(monkeypatch):
    db = FakeDB(facility=False)

    response = call_create(monkeypatch, db)

    assert response.status_code == 404
    assert response.json()["detail"] == "Facility not found"
    assert db.commit_count == 0
    assert db.added == []


def test_creation_rejects_missing_supplier(monkeypatch):
    db = FakeDB(supplier=False)

    response = call_create(monkeypatch, db)

    assert response.status_code == 404
    assert response.json()["detail"] == "Supplier not found"
    assert db.commit_count == 0
    assert db.added == []


def test_creation_rejects_missing_medicine(monkeypatch):
    db = FakeDB(medicines=[30])

    response = call_create(monkeypatch, db)

    assert response.status_code == 404
    assert "31" in response.json()["detail"]
    assert db.commit_count == 0
    assert db.added == []


def test_successful_creation_calculates_total_and_saves_items(monkeypatch):
    db = FakeDB()

    response = call_create(monkeypatch, db)

    assert response.status_code == 201
    body = response.json()

    assert body["message"] == "Purchase order created successfully"
    assert body["purchase_order_id"] == 100
    assert body["status"] == "DRAFT"
    assert Decimal(str(body["total_amount"])) == Decimal("225.00")

    order = next(
        entry for entry in db.added
        if isinstance(entry, PurchaseOrder)
    )
    items = [
        entry for entry in db.added
        if isinstance(entry, PurchaseOrderItem)
    ]

    assert order.facility_id == 10
    assert order.supplier_id == 20
    assert order.status == "DRAFT"
    assert order.total_amount == Decimal("225.00")
    assert order.remarks == "Urgent replenishment"

    assert len(items) == 2
    assert {
        (item.medicine_id, item.ordered_quantity, item.received_quantity)
        for item in items
    } == {
        (30, 10, 0),
        (31, 4, 0),
    }

    assert all(item.purchase_order_id == 100 for item in items)
    assert db.commit_count == 1
    assert db.rollback_count == 0
    assert db.refresh_count == 1


def test_creation_rolls_back_when_outbox_event_fails(monkeypatch):
    db = FakeDB()

    def fail_outbox(*args, **kwargs):
        raise RuntimeError("Outbox unavailable")

    with pytest.raises(RuntimeError, match="Outbox unavailable"):
        call_create(
            monkeypatch,
            db,
            outbox_handler=fail_outbox,
        )

    assert db.commit_count == 0
    assert db.rollback_count == 1

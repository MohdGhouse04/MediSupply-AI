from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db
from backend.app.api import purchase_orders


def make_order(status="DRAFT"):
    return SimpleNamespace(
        purchase_order_id=1,
        facility_id=10,
        supplier_id=20,
        status=status,
        approved_at=None,
        ordered_at=None,
        remarks="Original remarks",
    )


class FakeQuery:
    def __init__(self, order):
        self.order = order

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.order


class FakeDB:
    def __init__(self, order=None):
        self.order = order
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0

    def query(self, *args):
        return FakeQuery(self.order)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, instance):
        self.refresh_count += 1


def run_status_update(monkeypatch, fake_db, status, remarks=None):
    monkeypatch.setattr(
        purchase_orders,
        "add_outbox_event",
        lambda *args, **kwargs: None,
    )

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            return client.patch(
                "/purchase-orders/1/status",
                json={"status": status, "remarks": remarks},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    "old_status,new_status",
    [
        ("DRAFT", "PENDING_APPROVAL"),
        ("DRAFT", "CANCELLED"),
        ("PENDING_APPROVAL", "APPROVED"),
        ("PENDING_APPROVAL", "REJECTED"),
        ("PENDING_APPROVAL", "CANCELLED"),
        ("APPROVED", "ORDERED"),
        ("APPROVED", "CANCELLED"),
    ],
)
def test_allowed_purchase_order_transitions(
    monkeypatch, old_status, new_status
):
    order = make_order(old_status)
    db = FakeDB(order)

    response = run_status_update(monkeypatch, db, new_status)

    assert response.status_code == 200
    assert response.json()["old_status"] == old_status
    assert response.json()["new_status"] == new_status
    assert order.status == new_status
    assert db.commit_count == 1
    assert db.rollback_count == 0
    assert db.refresh_count == 1

    if new_status == "APPROVED":
        assert isinstance(order.approved_at, datetime)

    if new_status == "ORDERED":
        assert isinstance(order.ordered_at, datetime)


@pytest.mark.parametrize(
    "old_status,new_status",
    [
        ("DRAFT", "APPROVED"),
        ("PENDING_APPROVAL", "ORDERED"),
        ("APPROVED", "REJECTED"),
        ("ORDERED", "CANCELLED"),
        ("PARTIALLY_RECEIVED", "ORDERED"),
        ("RECEIVED", "CANCELLED"),
        ("REJECTED", "APPROVED"),
    ],
)
def test_invalid_purchase_order_transitions(
    monkeypatch, old_status, new_status
):
    order = make_order(old_status)
    db = FakeDB(order)

    response = run_status_update(monkeypatch, db, new_status)

    assert response.status_code == 409
    assert order.status == old_status
    assert db.commit_count == 0
    assert db.rollback_count == 0


def test_missing_purchase_order_returns_404(monkeypatch):
    db = FakeDB(order=None)

    response = run_status_update(
        monkeypatch, db, "PENDING_APPROVAL"
    )

    assert response.status_code == 404
    assert db.commit_count == 0


def test_status_update_saves_remarks(monkeypatch):
    order = make_order()
    db = FakeDB(order)

    response = run_status_update(
        monkeypatch, db, "PENDING_APPROVAL", "Reviewed"
    )

    assert response.status_code == 200
    assert order.remarks == "Reviewed"


def test_outbox_failure_rolls_back_status_update(monkeypatch):
    order = make_order()
    db = FakeDB(order)

    def fail_outbox(*args, **kwargs):
        raise RuntimeError("Outbox unavailable")

    monkeypatch.setattr(
        purchase_orders, "add_outbox_event", fail_outbox
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            with pytest.raises(RuntimeError, match="Outbox unavailable"):
                client.patch(
                    "/purchase-orders/1/status",
                    json={"status": "PENDING_APPROVAL"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert db.commit_count == 0
    assert db.rollback_count == 1

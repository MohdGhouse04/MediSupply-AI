from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db


def make_transfer(status="PENDING"):
    return SimpleNamespace(
        transfer_id=1,
        source_facility_id=1,
        destination_facility_id=2,
        batch_id=10,
        quantity=20,
        status=status,
        requested_at=datetime(2026, 11, 24, 10, 0),
        approved_at=None,
        dispatched_at=None,
        received_at=None,
        remarks="Test transfer",
    )


class FakeTransferDB:
    def __init__(self, transfer=None):
        self.transfer = transfer
        self.commit_count = 0
        self.rollback_count = 0

    def execute(self, statement):
        return SimpleNamespace(
            scalar_one_or_none=lambda: self.transfer
        )

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, instance):
        pass


def run_status_update(fake_db, status, remarks=None):
    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.patch(
                "/stock-transfers/1/status",
                json={"status": status, "remarks": remarks},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_approve_pending_transfer():
    transfer = make_transfer()
    fake_db = FakeTransferDB(transfer)

    response = run_status_update(fake_db, "APPROVED", "Approved for dispatch")

    assert response.status_code == 200
    assert transfer.status == "APPROVED"
    assert transfer.approved_at is not None
    assert transfer.remarks == "Approved for dispatch"
    assert fake_db.commit_count == 1
    assert fake_db.rollback_count == 0


def test_reject_pending_transfer():
    transfer = make_transfer()
    fake_db = FakeTransferDB(transfer)

    response = run_status_update(fake_db, "REJECTED")

    assert response.status_code == 200
    assert transfer.status == "REJECTED"
    assert fake_db.commit_count == 1


def test_cancel_approved_transfer():
    transfer = make_transfer("APPROVED")
    fake_db = FakeTransferDB(transfer)

    response = run_status_update(fake_db, "CANCELLED")

    assert response.status_code == 200
    assert transfer.status == "CANCELLED"
    assert fake_db.commit_count == 1


def test_cannot_approve_non_pending_transfer():
    transfer = make_transfer("DISPATCHED")
    fake_db = FakeTransferDB(transfer)

    response = run_status_update(fake_db, "APPROVED")

    assert response.status_code == 400
    assert transfer.status == "DISPATCHED"
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_cannot_cancel_dispatched_transfer():
    transfer = make_transfer("DISPATCHED")
    fake_db = FakeTransferDB(transfer)

    response = run_status_update(fake_db, "CANCELLED")

    assert response.status_code == 400
    assert transfer.status == "DISPATCHED"
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_status_update_returns_404_for_missing_transfer():
    fake_db = FakeTransferDB()

    response = run_status_update(fake_db, "APPROVED")

    assert response.status_code == 404
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


from datetime import date, timedelta


def make_batch():
    return SimpleNamespace(
        batch_id=10,
        batch_status="AVAILABLE",
        expires_on=date.today() + timedelta(days=100),
    )


def make_inventory(quantity=100, reserved=10, damaged=5):
    return SimpleNamespace(
        facility_id=1,
        batch_id=10,
        quantity_on_hand=quantity,
        reserved_quantity=reserved,
        damaged_quantity=damaged,
    )


class FakeTransferActionDB:
    def __init__(self, transfer, inventory=None, batch=None):
        self.transfer = transfer
        self.inventory = inventory
        self.batch = batch or make_batch()
        self.execute_count = 0
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0

    def execute(self, statement):
        self.execute_count += 1

        if self.execute_count == 1:
            result = self.transfer
        else:
            result = self.inventory

        return SimpleNamespace(
            scalar_one_or_none=lambda: result
        )

    def get(self, model, identifier):
        return self.batch

    def add(self, instance):
        self.added.append(instance)

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, instance):
        pass


def run_transfer_action(fake_db, action):
    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.post(f"/stock-transfers/1/{action}")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_successful_dispatch_deducts_stock_and_records_issued_transaction():
    transfer = make_transfer("APPROVED")
    inventory = make_inventory()
    fake_db = FakeTransferActionDB(transfer, inventory)

    response = run_transfer_action(fake_db, "dispatch")

    assert response.status_code == 200
    assert transfer.status == "DISPATCHED"
    assert transfer.dispatched_at is not None
    assert inventory.quantity_on_hand == 80
    assert fake_db.commit_count == 1
    assert fake_db.rollback_count == 0

    transactions = [
        item for item in fake_db.added
        if getattr(item, "transaction_type", None) == "ISSUED"
    ]
    assert len(transactions) == 1
    assert transactions[0].facility_id == 1
    assert transactions[0].batch_id == 10
    assert transactions[0].quantity == 20
    assert transactions[0].reference_number == "TRANSFER-1"


def test_dispatch_rejects_insufficient_usable_stock():
    transfer = make_transfer("APPROVED")
    inventory = make_inventory(quantity=30, reserved=10, damaged=5)
    fake_db = FakeTransferActionDB(transfer, inventory)

    response = run_transfer_action(fake_db, "dispatch")

    assert response.status_code == 400
    assert "Insufficient usable stock" in response.json()["detail"]
    assert transfer.status == "APPROVED"
    assert inventory.quantity_on_hand == 30
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1
    assert fake_db.added == []


def test_dispatch_rejects_pending_transfer():
    transfer = make_transfer("PENDING")
    inventory = make_inventory()
    fake_db = FakeTransferActionDB(transfer, inventory)

    response = run_transfer_action(fake_db, "dispatch")

    assert response.status_code == 400
    assert transfer.status == "PENDING"
    assert inventory.quantity_on_hand == 100
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_successful_receipt_adds_stock_and_records_received_transaction():
    transfer = make_transfer("DISPATCHED")
    inventory = make_inventory(
        quantity=40,
        reserved=5,
        damaged=5,
    )
    fake_db = FakeTransferActionDB(transfer, inventory)

    response = run_transfer_action(fake_db, "receive")

    assert response.status_code == 200
    assert transfer.status == "RECEIVED"
    assert transfer.received_at is not None
    assert inventory.quantity_on_hand == 60
    assert fake_db.commit_count == 1
    assert fake_db.rollback_count == 0

    transactions = [
        item for item in fake_db.added
        if getattr(item, "transaction_type", None) == "RECEIVED"
    ]
    assert len(transactions) == 1
    assert transactions[0].facility_id == 2
    assert transactions[0].batch_id == 10
    assert transactions[0].quantity == 20
    assert transactions[0].reference_number == "TRANSFER-1"


def test_receipt_creates_destination_inventory_when_missing():
    transfer = make_transfer("DISPATCHED")
    fake_db = FakeTransferActionDB(transfer, inventory=None)

    response = run_transfer_action(fake_db, "receive")

    assert response.status_code == 200
    assert transfer.status == "RECEIVED"
    assert fake_db.flush_count == 1
    assert fake_db.commit_count == 1

    from backend.app.models import Inventory

    inventories = [
        item for item in fake_db.added
        if isinstance(item, Inventory)
    ]
    assert len(inventories) == 1
    assert inventories[0].facility_id == 2
    assert inventories[0].batch_id == 10
    assert inventories[0].quantity_on_hand == 20
    assert inventories[0].reserved_quantity == 0
    assert inventories[0].damaged_quantity == 0


def test_receipt_rejects_transfer_not_yet_dispatched():
    transfer = make_transfer("APPROVED")
    fake_db = FakeTransferActionDB(transfer)

    response = run_transfer_action(fake_db, "receive")

    assert response.status_code == 400
    assert transfer.status == "APPROVED"
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1
    assert fake_db.added == []

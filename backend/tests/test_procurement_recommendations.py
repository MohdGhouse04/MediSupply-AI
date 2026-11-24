from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.models import Facility, Medicine, Inventory, StockTransfer
from backend.app.services import procurement_recommendation_service as service


class FakeQuery:
    def __init__(self, db, entities):
        self.db = db
        self.entities = entities

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        first = self.entities[0]

        if first is Facility:
            return self.db.facilities

        if first is Medicine:
            return self.db.medicines

        if first is Inventory.facility_id:
            return self.db.inventory_rows

        return self.db.transfer_rows


class FakeDB:
    def __init__(self, inventory_rows=None, transfer_rows=None):
        self.facilities = [
            SimpleNamespace(facility_id=1, facility_name="Facility A")
        ]
        self.medicines = [
            SimpleNamespace(
                medicine_id=10,
                generic_name="Test Medicine",
                strength="500 mg",
                unit="tablets",
            )
        ]
        self.inventory_rows = inventory_rows or []
        self.transfer_rows = transfer_rows or []

    def query(self, *entities):
        return FakeQuery(self, entities)


def forecast_data(demand_30=30):
    today = date.today()

    return pd.DataFrame([
        {
            "date": today + timedelta(days=1),
            "facility_id": 1,
            "medicine_id": 10,
            "predicted_demand": demand_30 * 7 / 30,
            "horizon": 7,
        },
        {
            "date": today + timedelta(days=1),
            "facility_id": 1,
            "medicine_id": 10,
            "predicted_demand": demand_30 * 14 / 30,
            "horizon": 14,
        },
        {
            "date": today + timedelta(days=1),
            "facility_id": 1,
            "medicine_id": 10,
            "predicted_demand": demand_30,
            "horizon": 30,
        },
    ])


def inventory_row(on_hand=40, reserved=5, damaged=3):
    return SimpleNamespace(
        facility_id=1,
        medicine_id=10,
        quantity_on_hand=on_hand,
        reserved_quantity=reserved,
        damaged_quantity=damaged,
    )


def transfer_row(status, quantity, source=2, destination=1):
    return SimpleNamespace(
        source_facility_id=source,
        destination_facility_id=destination,
        medicine_id=10,
        quantity=quantity,
        status=status,
    )


def run_recommendations(monkeypatch, db, demand_30=30, safety_days=3):
    monkeypatch.setattr(
        service,
        "load_forecasts",
        lambda: forecast_data(demand_30),
    )

    return service.get_procurement_recommendations(
        db,
        safety_days=safety_days,
    )


def test_procurement_accounts_for_reserved_damaged_and_approved_outgoing(
    monkeypatch,
):
    db = FakeDB(
        inventory_rows=[inventory_row()],
        transfer_rows=[
            transfer_row("APPROVED", 4, source=1, destination=2),
        ],
    )

    result = run_recommendations(monkeypatch, db)[0]

    assert result["usable_stock"] == 32
    assert result["planning_available_stock"] == 28
    assert result["approved_outgoing_transfer_quantity"] == 4
    assert result["required_stock"] == 33
    assert result["gross_procurement_gap"] == 5
    assert result["recommended_procurement_quantity"] == 5
    assert result["days_of_stock"] == 28
    assert result["urgency"] == "MEDIUM"
    assert result["action"] == "PROCUREMENT_RECOMMENDED"


def test_only_dispatched_inbound_reduces_provisional_procurement(
    monkeypatch,
):
    db = FakeDB(
        inventory_rows=[inventory_row()],
        transfer_rows=[
            transfer_row("PENDING", 10),
            transfer_row("APPROVED", 20),
            transfer_row("DISPATCHED", 2),
        ],
    )

    result = run_recommendations(monkeypatch, db)[0]

    assert result["pending_inbound_transfer_quantity"] == 10
    assert result["approved_inbound_transfer_quantity"] == 20
    assert result["dispatched_inbound_transfer_quantity"] == 2
    assert result["potential_inbound_transfer_quantity"] == 32
    assert result["gross_procurement_gap"] == 1
    assert result["provisional_procurement_quantity_after_transfers"] == 0
    assert result["action"] == "REVIEW_DISPATCHED_TRANSFER"


def test_sufficient_stock_returns_no_procurement_required(monkeypatch):
    db = FakeDB(
        inventory_rows=[inventory_row(on_hand=100, reserved=0, damaged=0)]
    )

    result = run_recommendations(monkeypatch, db)[0]

    assert result["gross_procurement_gap"] == 0
    assert result["recommended_procurement_quantity"] == 0
    assert result["action"] == "NO_PROCUREMENT_REQUIRED"


@pytest.mark.parametrize("safety_days", [-1, 31])
def test_invalid_safety_days_are_rejected(safety_days):
    with pytest.raises(ValueError, match="safety_days"):
        service.get_procurement_recommendations(
            FakeDB(),
            safety_days=safety_days,
        )

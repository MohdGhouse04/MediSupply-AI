from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db
from backend.app.api import expiry_management


class FakeDatabase:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, statement):
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(
                all=lambda: self.rows
            )
        )


def make_batch(
    batch_id,
    batch_number,
    expires_on,
    quantity,
    unit_cost=2.0
):
    return {
        "facility_id": 1,
        "facility_name": "Test Hospital",
        "medicine_id": 1,
        "generic_name": "Paracetamol",
        "strength": "650 mg",
        "batch_id": batch_id,
        "batch_number": batch_number,
        "expires_on": expires_on,
        "unit_cost": unit_cost,
        "quantity_on_hand": quantity,
        "reserved_quantity": 0,
        "damaged_quantity": 0
    }


def test_expiry_api_returns_fefo_recommendations(monkeypatch):
    today = date.today()

    rows = [
        make_batch(
            1,
            "BATCH-EXPIRING",
            today + timedelta(days=2),
            100
        ),
        make_batch(
            2,
            "BATCH-LATER",
            today + timedelta(days=40),
            50
        )
    ]

    forecast = {
        (1, 1): {
            today + timedelta(days=1): 30,
            today + timedelta(days=2): 20
        }
    }

    fake_db = FakeDatabase(rows)

    def override_get_db():
        yield fake_db

    monkeypatch.setattr(
        expiry_management,
        "load_60_day_forecasts",
        lambda: forecast
    )

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/expiry-management/recommendations"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["forecast_horizon_days"] == 60
    assert data["total_batches_reviewed"] == 2
    assert data["batches_with_insufficient_forecast"] == 1

    assert data["estimated_wastage_units"] == 50
    assert data["estimated_wastage_value"] == 100

    recommendations = {
        item["batch_id"]: item
        for item in data["recommendations"]
    }

    expiring_batch = recommendations[1]

    assert expiring_batch["projected_wastage_units"] == 50
    assert expiring_batch["forecast_status"] == (
        "ESTIMATED_WITHIN_60_DAY_FORECAST"
    )
    assert expiring_batch["recommendation"] == (
        "PRIORITIZE_ISSUE_OR_TRANSFER"
    )

    later_batch = recommendations[2]

    assert later_batch["projected_wastage_units"] is None
    assert later_batch["estimated_wastage_value"] is None
    assert later_batch["forecast_status"] == (
        "INSUFFICIENT_FORECAST_HORIZON"
    )


def test_expiry_api_handles_missing_forecast(monkeypatch):
    today = date.today()

    rows = [
        make_batch(
            3,
            "BATCH-NO-FORECAST",
            today + timedelta(days=10),
            75
        )
    ]

    fake_db = FakeDatabase(rows)

    def override_get_db():
        yield fake_db

    monkeypatch.setattr(
        expiry_management,
        "load_60_day_forecasts",
        lambda: {}
    )

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/expiry-management/recommendations"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["total_batches_reviewed"] == 1
    assert data["batches_with_insufficient_forecast"] == 1

    recommendation = data["recommendations"][0]

    assert recommendation["projected_wastage_units"] is None
    assert recommendation["estimated_wastage_value"] is None
    assert recommendation["forecast_status"] == (
        "NO_FORECAST_AVAILABLE"
    )
    assert recommendation["recommendation"] == (
        "REVIEW_FEFO_AND_MONITOR"
    )

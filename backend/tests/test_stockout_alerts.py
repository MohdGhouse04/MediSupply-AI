from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db
import backend.app.api.stockout_alerts as stockout_alerts


class FakeDatabase:
    def __init__(self, alert=None, rows=None):
        self.alert = alert
        self.rows = rows or []
        self.commit_count = 0
        self.rollback_count = 0

    def get(self, model, identity):
        return self.alert if self.alert and self.alert.alert_id == identity else None

    def execute(self, statement):
        return SimpleNamespace(all=lambda: self.rows, rowcount=1)

    def commit(self):
        self.commit_count += 1

    def refresh(self, instance):
        pass

    def rollback(self):
        self.rollback_count += 1


def make_alert():
    return SimpleNamespace(
        alert_id=1,
        source_date=date.today(),
        facility_id=1,
        medicine_id=1,
        stockout_probability=0.85,
        risk_threshold=0.70,
        risk_status="HIGH_RISK",
        alert_action="TRANSFER_STOCK",
        previous_stock=5,
        previous_unmet_demand=10,
        demand_rolling_mean_7=20,
        demand_rolling_mean_14=18,
        demand_rolling_mean_30=15,
        acknowledged=False,
        acknowledged_by=None,
        acknowledged_at=None,
    )


def test_whitespace_acknowledgement_is_rejected_without_mutation():
    alert = make_alert()
    fake_db = FakeDatabase(alert=alert)

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/stockout-alerts/1/acknowledge",
                json={"acknowledged_by": "   "},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert alert.acknowledged is False
    assert alert.acknowledged_by is None
    assert alert.acknowledged_at is None
    assert fake_db.commit_count == 0


def test_acknowledgement_rejects_missing_alert():
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/stockout-alerts/999/acknowledge",
                json={"acknowledged_by": "Test Operator"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert fake_db.commit_count == 0


def test_successful_acknowledgement_updates_alert():
    alert = make_alert()
    fake_db = FakeDatabase(alert=alert)

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/stockout-alerts/1/acknowledge",
                json={"acknowledged_by": "  Test Operator  "},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["acknowledged"] is True
    assert data["acknowledged_by"] == "Test Operator"
    assert data["acknowledged_at"] is not None

    assert alert.acknowledged is True
    assert alert.acknowledged_by == "Test Operator"
    assert alert.acknowledged_at is not None
    assert fake_db.commit_count == 1


def test_repeated_acknowledgement_preserves_original_details():
    alert = make_alert()
    alert.acknowledged = True
    alert.acknowledged_by = "Original Operator"

    from datetime import datetime

    original_timestamp = datetime(2026, 11, 20, 10, 30)
    alert.acknowledged_at = original_timestamp

    fake_db = FakeDatabase(alert=alert)

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/stockout-alerts/1/acknowledge",
                json={"acknowledged_by": "Another Operator"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["acknowledged"] is True
    assert data["acknowledged_by"] == "Original Operator"
    assert data["acknowledged_at"] == original_timestamp.isoformat()

    assert alert.acknowledged_by == "Original Operator"
    assert alert.acknowledged_at == original_timestamp
    assert fake_db.commit_count == 0


def test_stockout_alert_listing_returns_no_data_state():
    fake_db = FakeDatabase(rows=[])

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/stockout-alerts/")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["total_alerts"] == 0
    assert data["high_risk_count"] == 0
    assert data["low_risk_count"] == 0
    assert data["acknowledged_count"] == 0
    assert data["unacknowledged_count"] == 0
    assert data["source_date"] is None
    assert data["freshness_status"] == "NO_DATA"
    assert data["is_stale"] is True
    assert data["alerts"] == []


def test_stockout_alert_listing_calculates_summary_counts():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()

    high_acknowledged = make_alert()
    high_acknowledged.alert_id = 1
    high_acknowledged.source_date = today
    high_acknowledged.acknowledged = True
    high_acknowledged.acknowledged_by = "Operator A"

    high_unacknowledged = make_alert()
    high_unacknowledged.alert_id = 2
    high_unacknowledged.source_date = today
    high_unacknowledged.acknowledged = False

    low_unacknowledged = make_alert()
    low_unacknowledged.alert_id = 3
    low_unacknowledged.source_date = today
    low_unacknowledged.risk_status = "LOW_RISK"
    low_unacknowledged.acknowledged = False

    rows = [
        (high_acknowledged, "Facility A", "Medicine A", "500 mg", "Tablet"),
        (high_unacknowledged, "Facility B", "Medicine B", "250 mg", "Capsule"),
        (low_unacknowledged, "Facility A", "Medicine C", "100 mg", "Tablet"),
    ]

    fake_db = FakeDatabase(rows=rows)

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/stockout-alerts/")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    data = response.json()

    assert data["total_alerts"] == 3
    assert data["high_risk_count"] == 2
    assert data["low_risk_count"] == 1
    assert data["acknowledged_count"] == 1
    assert data["unacknowledged_count"] == 2

    assert data["source_date"] == today.isoformat()
    assert data["source_age_days"] == 0
    assert data["freshness_status"] == "FRESH"
    assert data["is_stale"] is False

    assert len(data["alerts"]) == 3
    assert data["alerts"][0]["facility_name"] == "Facility A"
    assert data["alerts"][0]["medicine"] == "Medicine A"
    assert data["alerts"][0]["acknowledged_by"] == "Operator A"


def test_stockout_alert_history_returns_records_and_filters():
    alert = make_alert()
    row = (alert, "Facility A", "Medicine A", "500 mg", "Tablet")
    fake_db = FakeDatabase(rows=[row])

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/stockout-alerts/history",
                params={
                    "facility_id": 1,
                    "medicine_id": 1,
                    "start_date": "2026-11-01",
                    "end_date": "2026-11-30",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()

    assert data["total_records"] == 1
    assert data["filters"] == {
        "facility_id": 1,
        "medicine_id": 1,
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
    }
    assert data["alerts"][0]["facility_name"] == "Facility A"
    assert data["alerts"][0]["medicine"] == "Medicine A"


def test_stockout_alert_history_rejects_reversed_dates():
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/stockout-alerts/history",
                params={
                    "start_date": "2026-11-25",
                    "end_date": "2026-11-20",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date cannot be later than end_date."


def test_stockout_alert_history_rejects_nonpositive_ids():
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/stockout-alerts/history",
                params={"facility_id": 0, "medicine_id": -1},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


def test_stockout_sync_returns_404_when_csv_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stockout_alerts,
        "ALERTS_PATH",
        tmp_path / "missing.csv",
    )
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post("/stockout-alerts/sync")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert fake_db.commit_count == 0


def test_stockout_sync_rejects_missing_csv_columns(tmp_path, monkeypatch):
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("date,facility_id\n2026-11-24,1\n")
    monkeypatch.setattr(stockout_alerts, "ALERTS_PATH", csv_path)

    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post("/stockout-alerts/sync")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert "Missing required CSV columns" in response.json()["detail"]
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_stockout_sync_rejects_empty_csv_records(tmp_path, monkeypatch):
    import csv

    csv_path = tmp_path / "empty.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=sorted(stockout_alerts.REQUIRED_COLUMNS),
        )
        writer.writeheader()

    monkeypatch.setattr(stockout_alerts, "ALERTS_PATH", csv_path)
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post("/stockout-alerts/sync")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert "CSV contains no alert records" in response.json()["detail"]
    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_stockout_sync_imports_valid_csv(tmp_path, monkeypatch):
    import csv

    csv_path = tmp_path / "valid.csv"
    fieldnames = sorted(stockout_alerts.REQUIRED_COLUMNS)

    record = {
        "date": "2026-11-24",
        "facility_id": "1",
        "medicine_id": "1",
        "stockout_probability": "0.85",
        "risk_threshold": "0.70",
        "risk_status": "HIGH_RISK",
        "alert_action": "TRANSFER_STOCK",
        "previous_stock": "5",
        "previous_unmet_demand": "10",
        "demand_rolling_mean_7": "20",
        "demand_rolling_mean_14": "18",
        "demand_rolling_mean_30": "15",
    }

    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(record)

    monkeypatch.setattr(stockout_alerts, "ALERTS_PATH", csv_path)
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post("/stockout-alerts/sync")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()

    assert data["processed_records"] == 1
    assert data["database_rows_affected"] == 1
    assert data["acknowledgements_preserved"] is True
    assert fake_db.commit_count == 1
    assert fake_db.rollback_count == 0

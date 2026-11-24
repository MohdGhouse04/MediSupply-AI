from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db


class FakeDatabase:
    def execute(self, statement):
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(
                all=lambda: []
            )
        )

    def get(self, model, identity):
        return object()


def test_static_inventory_routes_are_not_captured_by_facility_route():
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            responses = {
                path: client.get(path)
                for path in [
                    "/inventory/low-stock",
                    "/inventory/expiry-risk",
                    "/inventory/summary/medicines",
                ]
            }
    finally:
        app.dependency_overrides.pop(get_db, None)

    for path, response in responses.items():
        assert response.status_code == 200, (
            f"{path} returned HTTP {response.status_code}: "
            f"{response.text}"
        )


def test_facility_inventory_route_still_works():
    fake_db = FakeDatabase()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/inventory/1")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == []

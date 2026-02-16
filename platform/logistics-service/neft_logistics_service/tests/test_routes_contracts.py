from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ["LOGISTICS_PROVIDER"] = "mock"

from neft_logistics_service.main import app  # noqa: E402


def test_fleet_list_contract() -> None:
    client = TestClient(app)
    response = client.post("/v1/fleet/list", json={"limit": 10, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert set(["ok", "items", "total", "limit", "offset"]).issubset(payload.keys())


def test_fuel_consumption_contract() -> None:
    client = TestClient(app)
    response = client.post("/v1/fuel/consumption", json={"trip_id": "trip-1", "distance_km": 100, "vehicle_kind": "truck"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == "trip-1"
    assert "liters" in payload

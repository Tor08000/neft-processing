from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["LOGISTICS_PROVIDER"] = "mock"
os.environ["LOGISTICS_IDEMPOTENCY_DB_PATH"] = "/tmp/logistics-idempotency-test.sqlite3"

from neft_logistics_service.main import app  # noqa: E402


def test_trip_create_idempotency_replay() -> None:
    client = TestClient(app)
    payload = {"trip_id": "trip-100", "vehicle_id": "veh-1", "route_id": "route-1"}
    headers = {"Idempotency-Key": "trip-create-key-1"}

    first = client.post("/v1/trips/create", json=payload, headers=headers)
    second = client.post("/v1/trips/create", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["trip_id"] == second.json()["trip_id"]
    assert second.json()["idempotency_status"] == "replayed"

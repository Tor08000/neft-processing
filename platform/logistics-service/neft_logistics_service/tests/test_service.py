from __future__ import annotations

from fastapi.testclient import TestClient
from jsonschema import validate

from neft_logistics_service.main import app


def _eta_payload() -> dict:
    return {
        "route_id": "route-1",
        "points": [
            {"lat": 59.9, "lon": 30.3, "ts": "2025-01-10T10:00:00Z"},
            {"lat": 60.1, "lon": 30.5, "ts": "2025-01-10T11:00:00Z"},
        ],
        "vehicle": {"type": "truck", "fuel_type": "diesel"},
        "context": {"traffic": "normal", "weather": "clear"},
    }


def _deviation_payload() -> dict:
    return {
        "route_id": "route-1",
        "planned_polyline": [[59.9, 30.3], [60.1, 30.5]],
        "actual_point": {"lat": 60.2, "lon": 30.8},
        "threshold_meters": 500,
    }


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "logistics-service"


def test_metrics() -> None:
    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "logistics_compute_total" in response.text
    assert "logistics_provider_errors_total" in response.text


def test_eta() -> None:
    client = TestClient(app)
    response = client.post("/v1/eta", json=_eta_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["eta_minutes"] == 25
    assert payload["confidence"] == 0.84
    assert payload["explain"]["primary_reason"] == "NORMAL_TRAFFIC"


def test_deviation() -> None:
    client = TestClient(app)
    response = client.post("/v1/deviation", json=_deviation_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["deviation_meters"] == 19983
    assert payload["is_violation"] is True
    assert payload["confidence"] == 0.9


def test_eta_contract_schema() -> None:
    client = TestClient(app)
    response = client.post("/v1/eta", json=_eta_payload())
    assert response.status_code == 200

    schema = {
        "type": "object",
        "required": ["eta_minutes", "confidence", "provider", "explain"],
        "properties": {
            "eta_minutes": {"type": "integer"},
            "confidence": {"type": "number"},
            "provider": {"type": "string"},
            "explain": {
                "type": "object",
                "required": ["primary_reason"],
                "properties": {
                    "primary_reason": {"type": "string"},
                    "secondary": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "factors": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }
    validate(instance=response.json(), schema=schema)


def test_deviation_contract_schema() -> None:
    client = TestClient(app)
    response = client.post("/v1/deviation", json=_deviation_payload())
    assert response.status_code == 200

    schema = {
        "type": "object",
        "required": ["deviation_meters", "is_violation", "confidence", "explain"],
        "properties": {
            "deviation_meters": {"type": "integer"},
            "is_violation": {"type": "boolean"},
            "confidence": {"type": "number"},
            "explain": {
                "type": "object",
                "required": ["primary_reason"],
                "properties": {
                    "primary_reason": {"type": "string"},
                    "secondary": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "factors": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }
    validate(instance=response.json(), schema=schema)

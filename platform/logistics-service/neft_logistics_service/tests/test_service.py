import os

os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("LOGISTICS_PROVIDER", "mock")

import pytest
from fastapi.testclient import TestClient
from jsonschema import validate

from neft_logistics_service.main import app


@pytest.fixture(autouse=True)
def _default_compute_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_PROVIDER", "mock")
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "mock")
    monkeypatch.delenv("LOGISTICS_INTERNAL_TOKEN", raising=False)


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


def _explain_payload(kind: str, context: dict | None = None) -> dict:
    payload = {"kind": kind}
    if context is not None:
        payload["context"] = context
    return payload


def _preview_payload() -> dict:
    return {
        "route_id": "route-1",
        "points": [
            {"lat": 59.9, "lon": 30.3, "sequence": 0, "stop_id": "stop-1"},
            {"lat": 60.1, "lon": 30.5, "sequence": 1, "stop_id": "stop-2"},
        ],
        "vehicle": {"type": "truck", "fuel_type": "diesel"},
        "context": {"traffic": "normal", "weather": "clear"},
    }


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "logistics-service"
    assert response.json()["provider_modes"]["compute"] == "mock"
    assert response.json()["external_providers"][0]["provider"] == "logistics_transport"


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
    assert payload["provider"] == "mock"


def test_explain_eta() -> None:
    client = TestClient(app)
    response = client.post("/v1/explain", json=_explain_payload("eta", {"traffic": "normal", "weather": "clear"}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["explain"]["primary_reason"] == "NORMAL_TRAFFIC"


def test_explain_deviation() -> None:
    client = TestClient(app)
    response = client.post("/v1/explain", json=_explain_payload("deviation"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["explain"]["primary_reason"] == "ROUTE_ON_PATH"


def test_eta_uses_osrm_provider_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")
    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_duration",
        lambda self, points: 1800.0,
    )

    client = TestClient(app)
    response = client.post("/v1/eta", json=_eta_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "osrm"
    assert payload["eta_minutes"] == 30
    assert payload["explain"]["primary_reason"] == "OSRM_ROUTE"


def test_eta_surfaces_osrm_failure_as_provider_error(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")

    def _raise(self, points):
        raise RuntimeError("osrm_unavailable")

    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_duration",
        _raise,
    )

    client = TestClient(app)
    response = client.post("/v1/eta", json=_eta_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "provider_error"}


def test_deviation_uses_osrm_provider_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")
    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_geometry",
        lambda self, polyline: list(polyline),
    )

    client = TestClient(app)
    response = client.post("/v1/deviation", json=_deviation_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "osrm"
    assert payload["is_violation"] is True
    assert payload["confidence"] == 0.85
    assert payload["explain"]["primary_reason"] == "OSRM_GEOMETRY"


def test_deviation_surfaces_osrm_failure_as_provider_error(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")

    def _raise(self, polyline):
        raise RuntimeError("osrm_unavailable")

    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_geometry",
        _raise,
    )

    client = TestClient(app)
    response = client.post("/v1/deviation", json=_deviation_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "provider_error"}


def test_explain_eta_uses_osrm_provider_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")

    client = TestClient(app)
    response = client.post("/v1/explain", json=_explain_payload("eta", {"traffic": "normal", "weather": "clear"}))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "osrm"
    assert payload["explain"]["primary_reason"] == "OSRM_ROUTE"


def test_explain_deviation_uses_osrm_provider_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")

    client = TestClient(app)
    response = client.post("/v1/explain", json=_explain_payload("deviation"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "osrm"
    assert payload["explain"]["primary_reason"] == "OSRM_GEOMETRY"


def test_route_preview_uses_osrm_provider_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")
    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_preview",
        lambda self, points: {
            "geometry": [(59.9, 30.3), (60.0, 30.4), (60.1, 30.5)],
            "distance_km": 28.4,
            "duration_seconds": 2100.0,
        },
    )

    client = TestClient(app)
    response = client.post("/api/int/v1/routes/preview", json=_preview_payload())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "provider",
        "geometry",
        "distance_km",
        "eta_minutes",
        "confidence",
        "computed_at",
        "degraded",
        "degradation_reason",
    }
    assert payload["provider"] == "osrm"
    assert payload["distance_km"] == 28.4
    assert payload["eta_minutes"] == 35
    assert payload["confidence"] == 0.82
    assert payload["degraded"] is False
    assert payload["degradation_reason"] is None
    assert len(payload["geometry"]) == 3
    assert "route_snapshot_id" not in payload
    assert "snapshot_id" not in payload


def test_route_preview_surfaces_osrm_failure_as_provider_error(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")

    def _raise(self, points):
        raise RuntimeError("osrm_unavailable")

    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_preview",
        _raise,
    )

    client = TestClient(app)
    response = client.post("/api/int/v1/routes/preview", json=_preview_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "provider_error"}


def test_route_preview_disabled_compute_mode_returns_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "disabled")

    client = TestClient(app)
    response = client.post("/api/int/v1/routes/preview", json=_preview_payload())

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "category": "provider_unavailable",
        "error": "logistics_compute_disabled",
        "provider": "logistics_compute",
        "mode": "disabled",
        "retryable": False,
    }


def test_trip_status_disabled_transport_mode_returns_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_PROVIDER", "disabled")

    client = TestClient(app)
    response = client.get("/v1/trips/trip-1/status")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "category": "provider_unavailable",
        "error": "logistics_transport_disabled",
        "provider": "logistics_transport",
        "mode": "disabled",
        "retryable": False,
    }


def test_route_preview_requires_internal_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_INTERNAL_TOKEN", "preview-secret")
    monkeypatch.setenv("LOGISTICS_COMPUTE_PROVIDER", "osrm")
    monkeypatch.setattr(
        "neft_logistics_service.providers.osrm.OSRMProvider._fetch_route_preview",
        lambda self, points: {
            "geometry": [(59.9, 30.3), (60.1, 30.5)],
            "distance_km": 28.4,
            "duration_seconds": 2100.0,
        },
    )

    client = TestClient(app)
    response = client.post("/api/int/v1/routes/preview", json=_preview_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_internal_token"}


def test_route_preview_contract_schema() -> None:
    client = TestClient(app)
    response = client.post("/api/int/v1/routes/preview", json=_preview_payload())
    assert response.status_code == 200

    schema = {
        "type": "object",
        "required": [
            "provider",
            "geometry",
            "distance_km",
            "eta_minutes",
            "confidence",
            "computed_at",
            "degraded",
            "degradation_reason",
        ],
        "properties": {
            "provider": {"type": "string"},
            "geometry": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["lat", "lon"],
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                    },
                },
            },
            "distance_km": {"type": "number"},
            "eta_minutes": {"type": "integer"},
            "confidence": {"type": "number"},
            "computed_at": {"type": "string"},
            "degraded": {"type": "boolean"},
            "degradation_reason": {"type": ["string", "null"]},
        },
    }
    validate(instance=response.json(), schema=schema)


def test_route_preview_rejects_too_few_points() -> None:
    client = TestClient(app)
    payload = _preview_payload()
    payload["points"] = [payload["points"][0]]

    response = client.post("/api/int/v1/routes/preview", json=payload)

    assert response.status_code == 422


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
        "required": ["deviation_meters", "is_violation", "confidence", "provider", "explain"],
        "properties": {
            "deviation_meters": {"type": "integer"},
            "is_violation": {"type": "boolean"},
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


def test_explain_contract_schema() -> None:
    client = TestClient(app)
    response = client.post("/v1/explain", json=_explain_payload("eta", {"traffic": "normal"}))
    assert response.status_code == 200

    schema = {
        "type": "object",
        "required": ["provider", "explain"],
        "properties": {
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

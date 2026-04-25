from __future__ import annotations

import json
import os
import socket

import pytest

from neft_logistics_service.providers import get_compute_provider, get_transport_provider  # noqa: E402
from neft_logistics_service.providers.integration_hub_provider import IntegrationHubProvider  # noqa: E402
from neft_logistics_service.schemas import DeviationRequest, EtaRequest  # noqa: E402
from neft_logistics_service.schemas.trips import TripCreateRequest  # noqa: E402


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = {"X-Request-ID": "req-3"}

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _integration_hub_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_PROVIDER", "integration_hub")
    monkeypatch.setenv("LOGISTICS_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.delenv("LOGISTICS_COMPUTE_PROVIDER", raising=False)


def test_integration_hub_retries_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = IntegrationHubProvider()
    attempts = {"count": 0}

    def fake_urlopen(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise socket.timeout("timeout")
        return _Response({"ok": True, "trip_id": "trip-retry", "status": "created"})

    monkeypatch.setattr("neft_logistics_service.providers.integration_hub_provider.urllib_request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    response = provider.trip_create(TripCreateRequest(trip_id="trip-retry", vehicle_id="veh-1", route_id="route-1"))

    assert response.trip_id == "trip-retry"
    assert attempts["count"] == 3


def test_integration_hub_is_transport_only_provider() -> None:
    assert isinstance(get_transport_provider("integration_hub"), IntegrationHubProvider)
    with pytest.raises(ValueError, match="unsupported_compute_provider:integration_hub"):
        get_compute_provider("integration_hub")


def test_integration_hub_compute_methods_fail_clearly() -> None:
    provider = IntegrationHubProvider()
    eta_request = EtaRequest(
        route_id="route-1",
        points=[
            {"lat": 59.9, "lon": 30.3, "ts": "2025-01-10T10:00:00Z"},
            {"lat": 60.1, "lon": 30.5, "ts": "2025-01-10T11:00:00Z"},
        ],
        vehicle={"type": "truck", "fuel_type": "diesel"},
        context={"traffic": "normal", "weather": "clear"},
    )
    deviation_request = DeviationRequest(
        route_id="route-1",
        planned_polyline=[(59.9, 30.3), (60.1, 30.5)],
        actual_point={"lat": 60.2, "lon": 30.8},
        threshold_meters=500,
    )

    with pytest.raises(RuntimeError, match="compute_provider_unsupported:integration_hub"):
        provider.compute_eta(eta_request)
    with pytest.raises(RuntimeError, match="compute_provider_unsupported:integration_hub"):
        provider.compute_deviation(deviation_request)
    with pytest.raises(RuntimeError, match="compute_provider_unsupported:integration_hub"):
        provider.explain_eta(eta_request)
    with pytest.raises(RuntimeError, match="compute_provider_unsupported:integration_hub"):
        provider.explain_deviation(deviation_request)

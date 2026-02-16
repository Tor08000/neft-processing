from __future__ import annotations

import io
import json
import os
import socket

import pytest

os.environ["LOGISTICS_PROVIDER"] = "integration_hub"
os.environ["LOGISTICS_RETRY_MAX_ATTEMPTS"] = "3"

from neft_logistics_service.providers.integration_hub_provider import IntegrationHubProvider  # noqa: E402
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

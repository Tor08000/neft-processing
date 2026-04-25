from __future__ import annotations

import httpx

from app.services.logistics.service_client import LogisticsServiceClient
from app.services.logistics.service_client import httpx as service_httpx


class _CapturingClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.requests: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.response


def test_preview_route_maps_internal_contract_and_token(monkeypatch) -> None:
    monkeypatch.setenv("LOGISTICS_INTERNAL_TOKEN", "preview-secret")

    response = httpx.Response(
        200,
        request=httpx.Request("POST", "http://logistics-service:8000/api/int/v1/routes/preview"),
        json={
            "provider": "osrm",
            "geometry": [
                {"lat": 55.75, "lon": 37.6},
                {"lat": 55.76, "lon": 37.61},
            ],
            "distance_km": 15.5,
            "eta_minutes": 22,
            "confidence": 0.82,
            "computed_at": "2026-04-11T09:00:00Z",
            "degraded": False,
            "degradation_reason": None,
        },
    )
    capturing_client = _CapturingClient(response)
    monkeypatch.setattr(service_httpx, "Client", lambda *args, **kwargs: capturing_client)

    result = LogisticsServiceClient(base_url="http://logistics-service:8000").preview_route(
        {
            "route_id": "route-1",
            "points": [
                {"lat": 55.75, "lon": 37.6, "sequence": 0},
                {"lat": 55.76, "lon": 37.61, "sequence": 1},
            ],
            "vehicle": {"type": "truck", "fuel_type": "diesel"},
            "context": {},
        }
    )

    assert len(capturing_client.requests) == 1
    request = capturing_client.requests[0]
    assert request["url"] == "http://logistics-service:8000/api/int/v1/routes/preview"
    assert request["headers"] == {"X-Internal-Token": "preview-secret"}
    assert result.provider == "osrm"
    assert result.distance_km == 15.5
    assert result.eta_minutes == 22
    assert result.confidence == 0.82
    assert result.degraded is False
    assert result.degradation_reason is None
    assert result.geometry[0].lat == 55.75
    assert result.geometry[1].lon == 37.61
    assert result.computed_at.isoformat() == "2026-04-11T09:00:00+00:00"

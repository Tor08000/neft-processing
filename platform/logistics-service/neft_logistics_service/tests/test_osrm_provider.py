from __future__ import annotations

from neft_logistics_service.providers.osrm import OSRMProvider
from neft_logistics_service.schemas import DeviationRequest, EtaRequest


def _eta_request() -> EtaRequest:
    return EtaRequest(
        route_id="route-1",
        points=[
            {"lat": 59.9, "lon": 30.3, "ts": "2025-01-10T10:00:00Z"},
            {"lat": 60.1, "lon": 30.5, "ts": "2025-01-10T11:00:00Z"},
        ],
        vehicle={"type": "truck", "fuel_type": "diesel"},
        context={"traffic": "normal", "weather": "clear"},
    )


def _deviation_request() -> DeviationRequest:
    return DeviationRequest(
        route_id="route-1",
        planned_polyline=[(59.9, 30.3), (60.1, 30.5)],
        actual_point={"lat": 60.2, "lon": 30.8},
        threshold_meters=500,
    )


def test_osrm_eta_falls_back_to_mock(monkeypatch):
    provider = OSRMProvider()

    def _raise(*_args, **_kwargs):
        raise RuntimeError("osrm down")

    monkeypatch.setattr(provider, "_fetch_route_duration", _raise)

    response = provider.compute_eta(_eta_request())
    assert response.provider == "mock"


def test_osrm_deviation_falls_back_to_mock(monkeypatch):
    provider = OSRMProvider()

    def _raise(*_args, **_kwargs):
        raise RuntimeError("osrm down")

    monkeypatch.setattr(provider, "_fetch_route_geometry", _raise)

    response = provider.compute_deviation(_deviation_request())
    assert response.confidence in {0.9, 0.78}

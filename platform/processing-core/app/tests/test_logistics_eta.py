import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.logistics import LogisticsNavigatorExplainType
from app.services.logistics import repository
from app.services.logistics.service_client import ETAResult, RoutePreviewPoint, RoutePreviewResult
from app.tests._logistics_route_harness import logistics_client_context


@pytest.fixture(autouse=True)
def _default_logistics_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.delenv("LOGISTICS_INTERNAL_TOKEN", raising=False)


@pytest.fixture()
def logistics_client() -> Tuple[TestClient, sessionmaker]:
    with logistics_client_context() as ctx:
        yield ctx


def _seed_fleet(db: Session) -> Tuple[str, str]:
    vehicle = FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="ETA123",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="ETA Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return str(vehicle.id), str(driver.id)


def _create_order(client: TestClient, payload: dict) -> str:
    resp = client.post("/api/v1/logistics/orders", json=payload)
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_route_with_stops(client: TestClient, order_id: str) -> str:
    route_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/routes",
        json={"distance_km": 12.0, "planned_duration_minutes": 30},
    )
    assert route_resp.status_code == 200
    route_id = route_resp.json()["id"]
    activate_resp = client.post(f"/api/v1/logistics/routes/{route_id}/activate")
    assert activate_resp.status_code == 200
    stops_resp = client.post(
        f"/api/v1/logistics/routes/{route_id}/stops",
        json=[
            {
                "sequence": 0,
                "stop_type": "START",
                "name": "Start",
                "lat": 55.75,
                "lon": 37.6,
            },
            {
                "sequence": 1,
                "stop_type": "END",
                "name": "End",
                "lat": 55.76,
                "lon": 37.61,
            },
        ],
    )
    assert stops_resp.status_code == 200
    return route_id


def test_eta_planned(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    planned_end = datetime.now(timezone.utc) + timedelta(hours=2)
    order_id = _create_order(
        client,
        {
            "tenant_id": 1,
            "client_id": "client-1",
            "order_type": "TRIP",
            "status": "PLANNED",
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "planned_end_at": planned_end.isoformat(),
        },
    )

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    assert eta_resp.json()["method"] == "PLANNED"
    assert eta_resp.json()["eta_end_at"].startswith(planned_end.isoformat()[:19])


def test_eta_in_progress_with_speed(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    now = datetime.now(timezone.utc)
    planned_start = now - timedelta(minutes=30)
    planned_end = now + timedelta(minutes=30)
    order_id = _create_order(
        client,
        {
            "tenant_id": 1,
            "client_id": "client-1",
            "order_type": "DELIVERY",
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "planned_start_at": planned_start.isoformat(),
            "planned_end_at": planned_end.isoformat(),
        },
    )

    start_resp = client.post(f"/api/v1/logistics/orders/{order_id}/start")
    assert start_resp.status_code == 200

    tracking_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "LOCATION",
            "ts": now.isoformat(),
            "lat": 55.7,
            "lon": 37.6,
            "speed_kmh": 65.0,
        },
    )
    assert tracking_resp.status_code == 200

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    assert eta_resp.json()["method"] == "SIMPLE_SPEED"
    assert eta_resp.json()["eta_end_at"] is not None


def test_eta_completed(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    order_id = _create_order(
        client,
        {
            "tenant_id": 1,
            "client_id": "client-1",
            "order_type": "SERVICE",
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
        },
    )

    client.post(f"/api/v1/logistics/orders/{order_id}/start")
    complete_resp = client.post(f"/api/v1/logistics/orders/{order_id}/complete")
    assert complete_resp.status_code == 200
    actual_end_at = complete_resp.json()["actual_end_at"]

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    assert eta_resp.json()["eta_end_at"].startswith(actual_end_at[:19])


def test_eta_route_uses_preview_backed_snapshot_when_available(
    monkeypatch: pytest.MonkeyPatch,
    logistics_client: Tuple[TestClient, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=True),
    )
    monkeypatch.setattr(
        "app.services.logistics.eta.LogisticsServiceClient.compute_eta",
        lambda self, payload: ETAResult(
            eta_minutes=45,
            confidence=0.88,
            provider="osrm",
            explain={"primary_reason": "OSRM_ROUTE"},
        ),
    )
    monkeypatch.setattr(
        "app.services.logistics.navigator.explain.LogisticsServiceClient.preview_route",
        lambda self, payload: RoutePreviewResult(
            provider="osrm",
            geometry=(
                RoutePreviewPoint(lat=55.75, lon=37.6),
                RoutePreviewPoint(lat=55.755, lon=37.605),
                RoutePreviewPoint(lat=55.76, lon=37.61),
            ),
            distance_km=18.75,
            eta_minutes=27,
            confidence=0.82,
            computed_at=datetime.now(timezone.utc),
            degraded=False,
            degradation_reason=None,
        ),
    )

    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    order_id = _create_order(
        client,
        {
            "tenant_id": 1,
            "client_id": "client-1",
            "order_type": "TRIP",
            "status": "PLANNED",
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "planned_end_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        },
    )
    route_id = _create_route_with_stops(client, order_id)

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    assert eta_resp.json()["method"] == "PLANNED"
    assert eta_resp.json()["eta_confidence"] == 88

    with SessionLocal() as db:
        snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
        assert snapshot is not None
        assert snapshot.provider == "osrm"
        assert snapshot.distance_km == 18.75
        assert snapshot.eta_minutes == 27

        explains = repository.list_navigator_explains(
            db,
            route_snapshot_id=str(snapshot.id),
            explain_type=LogisticsNavigatorExplainType.ETA,
        )
        assert len(explains) == 1
        assert explains[0].payload["navigator"] == "osrm"
        assert explains[0].payload["method"] == "service_preview"
        assert "external_preview" in explains[0].payload["assumptions"]
        assert "snapshot_id" not in explains[0].payload


def test_eta_route_falls_back_to_local_snapshot_when_preview_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    logistics_client: Tuple[TestClient, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=True),
    )
    monkeypatch.setattr(
        "app.services.logistics.eta.LogisticsServiceClient.compute_eta",
        lambda self, payload: ETAResult(
            eta_minutes=45,
            confidence=0.88,
            provider="osrm",
            explain={"primary_reason": "OSRM_ROUTE"},
        ),
    )

    def _raise(self, payload):
        raise RuntimeError("logistics_service_unreachable")

    monkeypatch.setattr(
        "app.services.logistics.navigator.explain.LogisticsServiceClient.preview_route",
        _raise,
    )

    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    order_id = _create_order(
        client,
        {
            "tenant_id": 1,
            "client_id": "client-1",
            "order_type": "TRIP",
            "status": "PLANNED",
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "planned_end_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        },
    )
    route_id = _create_route_with_stops(client, order_id)

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    assert eta_resp.json()["eta_confidence"] == 88

    with SessionLocal() as db:
        snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
        assert snapshot is not None
        assert snapshot.provider == "noop"

        explains = repository.list_navigator_explains(
            db,
            route_snapshot_id=str(snapshot.id),
            explain_type=LogisticsNavigatorExplainType.ETA,
        )
        assert len(explains) >= 1
        assert any(explain.payload["navigator"] == "noop" for explain in explains)
        assert any(explain.payload["method"] == "straight_line" for explain in explains)
        assert any(
            "preview_fallback=logistics_service_unreachable" in explain.payload.get("assumptions", [])
            for explain in explains
        )

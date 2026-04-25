import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.logistics import LogisticsNavigatorExplainType
from app.services.logistics import repository
from app.services.logistics.service_client import RoutePreviewPoint, RoutePreviewResult
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
        plate_number="T123TT",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Tracker",
        status=FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return str(vehicle.id), str(driver.id)


def _create_order(client: TestClient, vehicle_id: str, driver_id: str) -> str:
    payload = {
        "tenant_id": 1,
        "client_id": "client-1",
        "order_type": "DELIVERY",
        "vehicle_id": vehicle_id,
        "driver_id": driver_id,
    }
    resp = client.post("/api/v1/logistics/orders", json=payload)
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_route_and_stop(client: TestClient, order_id: str) -> str:
    route_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/routes",
        json={"distance_km": 55.0, "planned_duration_minutes": 90},
    )
    assert route_resp.status_code == 200
    route_id = route_resp.json()["id"]
    stops_resp = client.post(
        f"/api/v1/logistics/routes/{route_id}/stops",
        json=[{"sequence": 0, "stop_type": "START", "name": "Depot"}],
    )
    assert stops_resp.status_code == 200
    return stops_resp.json()[0]["id"]


def _create_route_with_geometry(client: TestClient, order_id: str) -> str:
    route_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/routes",
        json={"distance_km": 55.0, "planned_duration_minutes": 90},
    )
    assert route_resp.status_code == 200
    route_id = route_resp.json()["id"]
    activate_resp = client.post(f"/api/v1/logistics/routes/{route_id}/activate")
    assert activate_resp.status_code == 200
    stops_resp = client.post(
        f"/api/v1/logistics/routes/{route_id}/stops",
        json=[
            {"sequence": 0, "stop_type": "START", "name": "Depot", "lat": 55.75, "lon": 37.6},
            {"sequence": 1, "stop_type": "END", "name": "Client", "lat": 55.76, "lon": 37.61},
        ],
    )
    assert stops_resp.status_code == 200
    return route_id


def test_tracking_events(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    order_id = _create_order(client, vehicle_id, driver_id)
    stop_id = _create_route_and_stop(client, order_id)

    base_ts = datetime.now(timezone.utc)
    event_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "LOCATION",
            "ts": base_ts.isoformat(),
            "lat": 55.75,
            "lon": 37.61,
        },
    )
    assert event_resp.status_code == 200

    arrival_ts = base_ts + timedelta(minutes=5)
    arrival_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "STOP_ARRIVAL",
            "ts": arrival_ts.isoformat(),
            "stop_id": stop_id,
        },
    )
    assert arrival_resp.status_code == 200

    departure_ts = base_ts + timedelta(minutes=12)
    departure_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "STOP_DEPARTURE",
            "ts": departure_ts.isoformat(),
            "stop_id": stop_id,
        },
    )
    assert departure_resp.status_code == 200

    list_resp = client.get(f"/api/v1/logistics/orders/{order_id}/tracking", params={"limit": 10})
    assert list_resp.status_code == 200
    events = list_resp.json()
    assert events[0]["ts"] >= events[1]["ts"]


def test_tracking_preview_backed_snapshot_keeps_local_deviation_evidence(
    monkeypatch: pytest.MonkeyPatch,
    logistics_client: Tuple[TestClient, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")
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

    order_id = _create_order(client, vehicle_id, driver_id)
    route_id = _create_route_with_geometry(client, order_id)

    base_ts = datetime.now(timezone.utc)
    first_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "LOCATION",
            "ts": base_ts.isoformat(),
            "lat": 55.75,
            "lon": 37.6,
        },
    )
    assert first_resp.status_code == 200

    second_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "LOCATION",
            "ts": (base_ts + timedelta(minutes=5)).isoformat(),
            "lat": 55.8,
            "lon": 37.7,
        },
    )
    assert second_resp.status_code == 200

    with SessionLocal() as db:
        snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
        assert snapshot is not None
        assert snapshot.provider == "osrm"

        explains = repository.list_navigator_explains(
            db,
            route_snapshot_id=str(snapshot.id),
            explain_type=LogisticsNavigatorExplainType.DEVIATION,
        )
        assert len(explains) == 1
        assert "score" in explains[0].payload
        assert "snapshot_id" not in explains[0].payload

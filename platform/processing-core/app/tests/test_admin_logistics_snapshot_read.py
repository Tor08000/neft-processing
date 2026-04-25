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
from app.tests._logistics_route_harness import admin_logistics_client_context


@pytest.fixture(autouse=True)
def _default_logistics_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.delenv("LOGISTICS_INTERNAL_TOKEN", raising=False)


@pytest.fixture()
def admin_logistics_client() -> Tuple[TestClient, sessionmaker]:
    with admin_logistics_client_context() as ctx:
        yield ctx


def _seed_fleet(db: Session) -> Tuple[str, str]:
    vehicle = FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="ADMIN123",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Admin Logistics Driver",
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


def test_admin_navigator_reads_preview_backed_local_snapshot_and_explain(
    monkeypatch: pytest.MonkeyPatch,
    admin_logistics_client: Tuple[TestClient, sessionmaker],
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

    client, SessionLocal = admin_logistics_client

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

    snapshot_resp = client.get(f"/api/core/v1/admin/logistics/routes/{route_id}/navigator")
    assert snapshot_resp.status_code == 200
    snapshot_payload = snapshot_resp.json()
    assert set(snapshot_payload) == {
        "id",
        "order_id",
        "route_id",
        "provider",
        "geometry",
        "distance_km",
        "eta_minutes",
        "created_at",
    }
    assert snapshot_payload["order_id"] == order_id
    assert snapshot_payload["route_id"] == route_id
    assert snapshot_payload["provider"] == "osrm"
    assert snapshot_payload["distance_km"] == 18.75
    assert snapshot_payload["eta_minutes"] == 27
    assert snapshot_payload["geometry"] == [
        {"lat": 55.75, "lon": 37.6},
        {"lat": 55.755, "lon": 37.605},
        {"lat": 55.76, "lon": 37.61},
    ]
    assert "snapshot_id" not in snapshot_payload

    explains_resp = client.get(f"/api/core/v1/admin/logistics/routes/{route_id}/navigator/explain")
    assert explains_resp.status_code == 200
    explains_payload = explains_resp.json()
    assert len(explains_payload) == 1
    explain_payload = explains_payload[0]
    assert set(explain_payload) == {"id", "route_snapshot_id", "type", "payload", "created_at"}
    assert explain_payload["type"] == LogisticsNavigatorExplainType.ETA.value
    assert explain_payload["route_snapshot_id"] == snapshot_payload["id"]
    assert explain_payload["payload"]["navigator"] == "osrm"
    assert explain_payload["payload"]["method"] == "service_preview"
    assert explain_payload["payload"]["distance_km"] == 18.75
    assert explain_payload["payload"]["eta_minutes"] == 27
    assert "external_preview" in explain_payload["payload"]["assumptions"]
    assert "compute_provider=osrm" in explain_payload["payload"]["assumptions"]
    assert "snapshot_id" not in explain_payload["payload"]

    with SessionLocal() as db:
        snapshot = repository.get_latest_route_snapshot(db, route_id=route_id)
        assert snapshot is not None
        assert str(snapshot.id) == snapshot_payload["id"]
        explains = repository.list_navigator_explains(
            db,
            route_snapshot_id=str(snapshot.id),
            explain_type=LogisticsNavigatorExplainType.ETA,
        )
        assert len(explains) == 1
        assert str(explains[0].route_snapshot_id) == explain_payload["route_snapshot_id"]


def test_admin_logistics_inspection_returns_grounded_order_route_and_tracking_context(
    monkeypatch: pytest.MonkeyPatch,
    admin_logistics_client: Tuple[TestClient, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=True),
    )
    monkeypatch.setattr(
        "app.services.logistics.eta.LogisticsServiceClient.compute_eta",
        lambda self, payload: ETAResult(
            eta_minutes=35,
            confidence=0.91,
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
                RoutePreviewPoint(lat=55.76, lon=37.61),
            ),
            distance_km=16.2,
            eta_minutes=25,
            confidence=0.83,
            computed_at=datetime.now(timezone.utc),
            degraded=False,
            degradation_reason=None,
        ),
    )

    client, SessionLocal = admin_logistics_client

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
            "planned_end_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
        },
    )
    route_id = _create_route_with_stops(client, order_id)

    eta_resp = client.get(f"/api/v1/logistics/orders/{order_id}/eta")
    assert eta_resp.status_code == 200
    tracking_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/tracking",
        json={
            "event_type": "LOCATION",
            "ts": datetime.now(timezone.utc).isoformat(),
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "lat": 55.755,
            "lon": 37.605,
            "speed_kmh": 42.0,
        },
    )
    assert tracking_resp.status_code == 200

    inspection_resp = client.get(f"/api/core/v1/admin/logistics/orders/{order_id}/inspection")

    assert inspection_resp.status_code == 200
    payload = inspection_resp.json()
    assert payload["order"]["id"] == order_id
    assert payload["order"]["status"] == "PLANNED"
    assert payload["active_route"]["id"] == route_id
    assert len(payload["routes"]) == 1
    assert len(payload["active_route_stops"]) == 2
    assert payload["latest_eta_snapshot"]["order_id"] == order_id
    assert payload["latest_route_snapshot"]["route_id"] == route_id
    assert payload["tracking_events_count"] == 1
    assert payload["last_tracking_event"]["event_type"] == "LOCATION"
    assert payload["navigator_explains"][0]["type"] == LogisticsNavigatorExplainType.ETA.value
    assert payload["navigator_explains"][0]["payload"]["navigator"] == "osrm"


def test_admin_logistics_inspection_denies_finance_only_admin() -> None:
    with admin_logistics_client_context(
        admin_claims={
            "user_id": "finance-admin-1",
            "sub": "finance-admin-1",
            "email": "finance-admin@example.com",
            "roles": ["NEFT_FINANCE"],
        }
    ) as (client, _SessionLocal):
        response = client.get("/api/core/v1/admin/logistics/orders/order-1/inspection")

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden_admin_role"

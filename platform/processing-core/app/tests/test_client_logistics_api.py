from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.client_logistics as client_logistics_module
from app.db import Base, get_db
from app.fastapi_utils import generate_unique_id
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionAuthType,
    FuelTransactionStatus,
    FuelType,
)
from app.models.logistics import (
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsETAMethod,
    LogisticsETASnapshot,
    LogisticsFuelAlert,
    LogisticsFuelAlertSeverity,
    LogisticsFuelAlertStatus,
    LogisticsFuelAlertType,
    LogisticsFuelLink,
    LogisticsFuelLinkedBy,
    LogisticsFuelLinkReason,
    LogisticsNavigatorExplain,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsRoute,
    LogisticsRouteSnapshot,
    LogisticsRouteStatus,
    LogisticsStop,
    LogisticsStopStatus,
    LogisticsStopType,
    LogisticsTrackingEvent,
    LogisticsTrackingEventType,
)
from app.routers.client_logistics import router as client_logistics_router
from app.services.logistics import repository as logistics_repository
from app.services.logistics.service_client import RoutePreviewPoint, RoutePreviewResult
from app.tests._logistics_route_harness import LOGISTICS_FUEL_TEST_TABLES


@contextmanager
def client_logistics_context() -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    Base.metadata.create_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_logistics_router, prefix="/api/core")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[client_logistics_module.require_client_user] = lambda: {"client_id": "client-1", "sub": "client-user-1"}

    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine, tables=LOGISTICS_FUEL_TEST_TABLES)
        engine.dispose()


def test_logistics_id_filters_compile_as_legacy_varchar_safe() -> None:
    order_filter = logistics_repository.id_equals(
        LogisticsOrder.id,
        "11111111-1111-1111-1111-111111111111",
    )
    route_filter = logistics_repository.ids_match(LogisticsRoute.id, LogisticsStop.route_id)

    compiled_order_filter = str(order_filter.compile(dialect=postgresql.dialect()))
    compiled_route_filter = str(route_filter.compile(dialect=postgresql.dialect()))

    assert "CAST(logistics_orders.id AS VARCHAR)" in compiled_order_filter
    assert "CAST(logistics_routes.id AS VARCHAR)" in compiled_route_filter
    assert "CAST(logistics_stops.route_id AS VARCHAR)" in compiled_route_filter
    assert "::UUID" not in compiled_order_filter


def _seed_fleet(db: Session) -> tuple[str, str]:
    vehicle_id = str(uuid4())
    driver_id = str(uuid4())
    db.add_all([
        FleetVehicle(
            id=vehicle_id,
            tenant_id=1,
            client_id="client-1",
            plate_number="A777AA77",
            vin="VIN-CREATE-1",
            brand="Kamaz",
            model="5490",
            fuel_type_preferred="DIESEL",
            status=FleetVehicleStatus.ACTIVE,
        ),
        FleetDriver(
            id=driver_id,
            tenant_id=1,
            client_id="client-1",
            full_name="Create Driver",
            phone="+79990000001",
            status=FleetDriverStatus.ACTIVE,
        ),
    ])
    db.commit()
    return vehicle_id, driver_id


def _seed_trip(db: Session) -> tuple[str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    vehicle_id = str(uuid4())
    driver_id = str(uuid4())
    trip_id = str(uuid4())
    route_id = str(uuid4())
    network_id = str(uuid4())
    station_id = str(uuid4())
    card_id = str(uuid4())
    other_card_id = str(uuid4())
    fuel_tx_id = str(uuid4())
    other_fuel_tx_id = str(uuid4())
    vehicle = FleetVehicle(id=vehicle_id, tenant_id=1, client_id="client-1", plate_number="A123BC77", vin="VIN-1", brand="Kamaz", model="5490", fuel_type_preferred="DIESEL", status=FleetVehicleStatus.ACTIVE)
    driver = FleetDriver(id=driver_id, tenant_id=1, client_id="client-1", full_name="Ivan Ivanov", phone="+79990000000", status=FleetDriverStatus.ACTIVE)
    order = LogisticsOrder(id=trip_id, tenant_id=1, client_id="client-1", order_type=LogisticsOrderType.TRIP, status=LogisticsOrderStatus.PLANNED, vehicle_id=vehicle_id, driver_id=driver_id, planned_start_at=now, planned_end_at=now + timedelta(hours=4), origin_text="Moscow", destination_text="Tula", meta={"title": "Morning route"})
    route = LogisticsRoute(id=route_id, order_id=trip_id, version=1, status=LogisticsRouteStatus.ACTIVE, distance_km=180.5, planned_duration_minutes=240)
    network = FuelNetwork(id=network_id, name="Seeded network", provider_code="GN4", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(id=station_id, network_id=network_id, name="Seeded station", city="Moscow", lat=55.75, lon=37.61, station_code="ST-1", status=FuelStationStatus.ACTIVE)
    card = FuelCard(id=card_id, tenant_id=1, client_id="client-1", card_token="card-token-1", card_alias="CARD-1", status=FuelCardStatus.ACTIVE)
    other_card = FuelCard(id=other_card_id, tenant_id=1, client_id="client-2", card_token="card-token-2", card_alias="CARD-2", status=FuelCardStatus.ACTIVE)
    tx = FuelTransaction(id=fuel_tx_id, tenant_id=1, client_id="client-1", card_id=card_id, vehicle_id=vehicle_id, driver_id=driver_id, station_id=station_id, network_id=network_id, occurred_at=now + timedelta(minutes=90), fuel_type=FuelType.DIESEL, volume_ml=40000, unit_price_minor=80, amount_total_minor=3200, currency="RUB", status=FuelTransactionStatus.SETTLED, auth_type=FuelTransactionAuthType.ONLINE, merchant_name="AZS-1", location="Moscow")
    other_tx = FuelTransaction(id=other_fuel_tx_id, tenant_id=1, client_id="client-2", card_id=other_card_id, station_id=station_id, network_id=network_id, occurred_at=now + timedelta(minutes=95), fuel_type=FuelType.DIESEL, volume_ml=15000, unit_price_minor=80, amount_total_minor=1200, currency="RUB", status=FuelTransactionStatus.SETTLED, auth_type=FuelTransactionAuthType.ONLINE, merchant_name="AZS-2", location="Ryazan")
    db.add_all([
        vehicle,
        driver,
        order,
        route,
        LogisticsStop(id=str(uuid4()), route_id=route_id, sequence=0, stop_type=LogisticsStopType.START, name="Moscow", lat=55.75, lon=37.61, planned_arrival_at=now, status=LogisticsStopStatus.PENDING),
        LogisticsStop(id=str(uuid4()), route_id=route_id, sequence=1, stop_type=LogisticsStopType.END, name="Tula", lat=54.2, lon=37.62, planned_arrival_at=now + timedelta(hours=4), status=LogisticsStopStatus.PENDING),
        LogisticsTrackingEvent(id=str(uuid4()), order_id=trip_id, vehicle_id=vehicle_id, driver_id=driver_id, event_type=LogisticsTrackingEventType.LOCATION, ts=now + timedelta(minutes=20), lat=55.80, lon=37.70, speed_kmh=52.3, heading_deg=180.0, meta={"accuracy_m": 12}),
        LogisticsETASnapshot(id=str(uuid4()), order_id=trip_id, computed_at=now + timedelta(minutes=30), eta_end_at=now + timedelta(hours=2), eta_confidence=82, method=LogisticsETAMethod.SIMPLE_SPEED, inputs={"source": "test"}),
        LogisticsDeviationEvent(id=str(uuid4()), order_id=trip_id, route_id=route_id, event_type=LogisticsDeviationEventType.OFF_ROUTE, ts=now + timedelta(minutes=40), lat=55.9, lon=37.8, distance_from_route_m=1500, severity=LogisticsDeviationSeverity.MEDIUM, explain={"title": "Route deviation", "details": "Driver left the planned corridor", "consequence": "ops_review"}),
        network,
        station,
        card,
        other_card,
        tx,
        other_tx,
        LogisticsFuelLink(id=str(uuid4()), client_id="client-1", trip_id=trip_id, fuel_tx_id=fuel_tx_id, score=95, reason=LogisticsFuelLinkReason.MANUAL_LINK, linked_by=LogisticsFuelLinkedBy.USER),
        LogisticsFuelAlert(id=str(uuid4()), client_id="client-1", trip_id=trip_id, fuel_tx_id=fuel_tx_id, type=LogisticsFuelAlertType.OUT_OF_ROUTE, severity=LogisticsFuelAlertSeverity.WARN, title="Fuel alert", details="Out of route", evidence={"distance_km": 3.2}, status=LogisticsFuelAlertStatus.OPEN),
    ])
    db.commit()
    return trip_id, fuel_tx_id


def test_client_logistics_routes_use_persisted_runtime_truth() -> None:
    with client_logistics_context() as (client, session_local):
        with session_local() as db:
            trip_id, fuel_tx_id = _seed_trip(db)

        fleet = client.get("/api/core/client/logistics/fleet")
        drivers = client.get("/api/core/client/logistics/fleet/drivers")
        trips = client.get("/api/core/client/logistics/trips")
        trip = client.get(f"/api/core/client/logistics/trips/{trip_id}")
        route = client.get(f"/api/core/client/logistics/trips/{trip_id}/route")
        tracking = client.get(f"/api/core/client/logistics/trips/{trip_id}/tracking")
        position = client.get(f"/api/core/client/logistics/trips/{trip_id}/position")
        eta = client.get(f"/api/core/client/logistics/trips/{trip_id}/eta")
        deviations = client.get(f"/api/core/client/logistics/trips/{trip_id}/deviations")
        impact = client.get(f"/api/core/client/logistics/trips/{trip_id}/sla-impact")
        fuel = client.get(f"/api/core/client/logistics/trips/{trip_id}/fuel")
        fuel_feed = client.get("/api/core/client/logistics/fuel")

    assert fleet.status_code == 200 and fleet.json()["items"][0]["plate"] == "A123BC77"
    assert drivers.status_code == 200 and drivers.json()["items"][0]["name"] == "Ivan Ivanov"
    assert trips.status_code == 200 and trips.json()["items"][0]["status"] == "CREATED"
    assert trip.status_code == 200 and trip.json()["route"]["stops"][0]["label"] == "Moscow"
    assert route.status_code == 200 and route.json()["distance_km"] == 180.5
    assert tracking.status_code == 200 and tracking.json()["last"]["lat"] == 55.8
    assert position.status_code == 200 and position.json()["speed_kmh"] == 52.3
    assert eta.status_code == 200 and eta.json()["confidence"] == 82
    assert deviations.status_code == 200 and deviations.json()["items"][0]["type"] == "ROUTE_DEVIATION"
    assert impact.status_code == 200 and impact.json()["impact_level"] == "MEDIUM"
    assert fuel.status_code == 200 and fuel.json()["totals"]["liters"] == 40.0
    assert fuel_feed.status_code == 200 and [row["fuel_tx_id"] for row in fuel_feed.json()["items"]] == [fuel_tx_id]


def test_client_logistics_trip_create_persists_route_and_external_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_payloads: list[dict] = []
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")

    def _preview_route(_self, payload: dict) -> RoutePreviewResult:
        preview_payloads.append(payload)
        return RoutePreviewResult(
            provider="osrm",
            geometry=(
                RoutePreviewPoint(lat=55.75, lon=37.61),
                RoutePreviewPoint(lat=55.0, lon=37.62),
                RoutePreviewPoint(lat=54.2, lon=37.62),
            ),
            distance_km=181.25,
            eta_minutes=210,
            confidence=0.91,
            computed_at=datetime.now(timezone.utc),
            degraded=False,
            degradation_reason=None,
        )

    monkeypatch.setattr(
        "app.services.logistics.navigator.explain.LogisticsServiceClient.preview_route",
        _preview_route,
    )

    with client_logistics_context() as (client, session_local):
        with session_local() as db:
            vehicle_id, driver_id = _seed_fleet(db)

        planned_start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
        create_resp = client.post(
            "/api/core/client/logistics/trips",
            json={
                "title": "Created from client",
                "vehicle_id": vehicle_id,
                "driver_id": driver_id,
                "start_planned_at": planned_start.isoformat(),
                "end_planned_at": (planned_start + timedelta(hours=4)).isoformat(),
                "origin": {"label": "Moscow", "lat": 55.75, "lon": 37.61},
                "destination": {"label": "Tula", "lat": 54.2, "lon": 37.62},
                "stops": [{"label": "Serpukhov", "lat": 54.92, "lon": 37.41}],
                "meta": {"dispatch_ref": "DISP-1"},
            },
        )

        assert create_resp.status_code == 201
        payload = create_resp.json()
        assert payload["status"] == "CREATED"
        assert payload["title"] == "Created from client"
        assert payload["vehicle"]["plate"] == "A777AA77"
        assert payload["driver"]["name"] == "Create Driver"
        assert payload["route"]["distance_km"] == 181.25
        assert payload["route"]["eta_minutes"] == 210
        assert [stop["type"] for stop in payload["route"]["stops"]] == ["START", "STOP", "END"]

        with session_local() as db:
            order = db.query(LogisticsOrder).filter(LogisticsOrder.id == payload["id"]).one()
            snapshot = db.query(LogisticsRouteSnapshot).filter(LogisticsRouteSnapshot.order_id == order.id).one()
            explain = db.query(LogisticsNavigatorExplain).filter(LogisticsNavigatorExplain.route_snapshot_id == snapshot.id).one()

    assert order.client_id == "client-1"
    assert order.order_type == LogisticsOrderType.TRIP
    assert order.status == LogisticsOrderStatus.PLANNED
    assert order.meta["source"] == "client_portal"
    assert order.meta["route_preview_owner"] == "logistics_service"
    assert snapshot.provider == "osrm"
    assert snapshot.distance_km == 181.25
    assert explain.payload["method"] == "service_preview"
    assert "external_preview" in explain.payload["assumptions"]
    assert preview_payloads and preview_payloads[0]["route_id"] == payload["route_id"]
    assert len(preview_payloads[0]["points"]) == 3


def test_client_logistics_fuel_consumption_analytics_and_provider_write(monkeypatch: pytest.MonkeyPatch) -> None:
    provider_payloads: list[dict] = []

    def _fuel_consumption(_self, payload: dict, *, idempotency_key: str | None = None) -> dict:
        provider_payloads.append({"payload": payload, "idempotency_key": idempotency_key})
        return {
            "ok": True,
            "request_id": "logistics-fuel-1",
            "trip_id": payload["trip_id"],
            "liters": 50.4,
            "method": "integration_hub",
            "provider_mode": "sandbox",
            "sandbox_proof": {"contract": "fuel_consumption.v1"},
            "last_attempt": {"attempt": 1, "status": "success"},
            "retryable": False,
            "idempotency_key": idempotency_key,
            "idempotency_status": "new",
        }

    monkeypatch.setattr(
        "app.routers.client_logistics.LogisticsServiceClient.fuel_consumption",
        _fuel_consumption,
    )
    with client_logistics_context() as (client, session_local):
        with session_local() as db:
            trip_id, _fuel_tx_id = _seed_trip(db)
            date_from = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            date_to = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        consumption_resp = client.get(
            "/api/core/client/logistics/fuel/consumption",
            params={"date_from": date_from, "date_to": date_to, "group_by": "trip"},
        )
        consumption_write_resp = client.post(
            "/api/core/client/logistics/fuel/consumption",
            json={"trip_id": trip_id, "distance_km": 180, "vehicle_kind": "truck"},
        )
        missing_trip = client.get(f"/api/core/client/logistics/trips/{uuid4()}")
        invalid_trip = client.get("/api/core/client/logistics/trips/missing-trip")

    assert consumption_resp.status_code == 200
    assert consumption_resp.json()["source"] == "persisted_fuel_links"
    assert consumption_resp.json()["totals"]["liters"] == 40.0
    assert consumption_resp.json()["totals"]["tx_count"] == 1
    assert consumption_write_resp.status_code == 200
    assert consumption_write_resp.json()["source"] == "logistics_service"
    assert consumption_write_resp.json()["provider_mode"] == "sandbox"
    assert consumption_write_resp.json()["audit_event_id"]
    assert provider_payloads and provider_payloads[0]["payload"]["trip_id"] == trip_id
    assert missing_trip.status_code == 404
    assert invalid_trip.status_code == 404


def test_client_logistics_fuel_reads_remain_compatible_with_legacy_storage_without_auth_type() -> None:
    with client_logistics_context() as (client, session_local):
        with session_local() as db:
            trip_id, _fuel_tx_id = _seed_trip(db)
            db.execute(text("ALTER TABLE fuel_transactions DROP COLUMN auth_type"))
            db.commit()
            date_from = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            date_to = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        trip_fuel = client.get(f"/api/core/client/logistics/trips/{trip_id}/fuel")
        fuel_feed = client.get("/api/core/client/logistics/fuel")
        unlinked = client.get(
            "/api/core/client/logistics/fuel/unlinked",
            params={"date_from": date_from, "date_to": date_to},
        )
        report = client.get(
            "/api/core/client/logistics/reports/fuel",
            params={"date_from": date_from, "date_to": date_to, "group_by": "trip"},
        )
        linker = client.post(
            "/api/core/client/logistics/fuel/linker:run",
            params={"date_from": date_from, "date_to": date_to},
        )

    assert trip_fuel.status_code == 200
    assert fuel_feed.status_code == 200
    assert unlinked.status_code == 200
    assert report.status_code == 200
    assert linker.status_code == 200

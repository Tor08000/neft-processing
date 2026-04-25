import os
from datetime import datetime, timezone
from typing import Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.db import Base
from app.models import audit_log as audit_models
from app.models import fleet as fleet_models
from app.models import fuel as fuel_models
from app.models import legal_graph as legal_models
from app.models import logistics as logistics_models
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics import navigator, repository, routes
from app.services.logistics.navigator import registry
from app.services.logistics.orders import create_order
from app.services.logistics.service_client import RoutePreviewPoint, RoutePreviewResult


# Register the nullable logistics stop FK target without creating the whole fuel domain graph.
_ = fuel_models.FuelTransaction.__table__
_TEST_TABLES = [
    audit_models.AuditLog.__table__,
    legal_models.LegalNode.__table__,
    legal_models.LegalEdge.__table__,
    fleet_models.FleetVehicle.__table__,
    fleet_models.FleetDriver.__table__,
    logistics_models.LogisticsOrder.__table__,
    logistics_models.LogisticsRoute.__table__,
    logistics_models.LogisticsStop.__table__,
    logistics_models.LogisticsRouteSnapshot.__table__,
    logistics_models.LogisticsNavigatorExplain.__table__,
]


@pytest.fixture(autouse=True)
def _default_logistics_preview_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.delenv("LOGISTICS_INTERNAL_TOKEN", raising=False)


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=_TEST_TABLES)
    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=_TEST_TABLES)
        engine.dispose()


def _seed_order(db: Session) -> logistics_models.LogisticsOrder:
    vehicle = fleet_models.FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="NAV123",
        status=fleet_models.FleetVehicleStatus.ACTIVE,
    )
    driver = fleet_models.FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Navigator Driver",
        status=fleet_models.FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.DELIVERY,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
    )


def test_route_snapshot_created(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    order = _seed_order(db)
    route = routes.create_route(db, order_id=str(order.id), distance_km=12.0, planned_duration_minutes=30)
    routes.upsert_stops(
        db,
        route_id=str(route.id),
        stops=[
            LogisticsStopIn(
                sequence=0,
                stop_type=logistics_models.LogisticsStopType.START,
                name="Start",
                lat=55.75,
                lon=37.6,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
            LogisticsStopIn(
                sequence=1,
                stop_type=logistics_models.LogisticsStopType.END,
                name="End",
                lat=55.76,
                lon=37.61,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
        ],
    )
    snapshot = repository.get_latest_route_snapshot(db, route_id=str(route.id))
    assert snapshot is not None
    assert snapshot.provider == "noop"
    assert snapshot.distance_km > 0


def test_route_snapshot_uses_logistics_service_preview_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Tuple[Session, sessionmaker],
) -> None:
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

    db, _ = db_session
    order = _seed_order(db)
    route = routes.create_route(db, order_id=str(order.id), distance_km=12.0, planned_duration_minutes=30)
    routes.upsert_stops(
        db,
        route_id=str(route.id),
        stops=[
            LogisticsStopIn(
                sequence=0,
                stop_type=logistics_models.LogisticsStopType.START,
                name="Start",
                lat=55.75,
                lon=37.6,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
            LogisticsStopIn(
                sequence=1,
                stop_type=logistics_models.LogisticsStopType.END,
                name="End",
                lat=55.76,
                lon=37.61,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
        ],
    )

    snapshot = repository.get_latest_route_snapshot(db, route_id=str(route.id))
    assert snapshot is not None
    assert snapshot.provider == "osrm"
    assert snapshot.distance_km == 18.75
    assert snapshot.eta_minutes == 27
    assert len(snapshot.geometry) == 3

    explains = repository.list_navigator_explains(
        db,
        route_snapshot_id=str(snapshot.id),
        explain_type=logistics_models.LogisticsNavigatorExplainType.ETA,
    )
    assert len(explains) == 1
    assert explains[0].payload["navigator"] == "osrm"
    assert explains[0].payload["method"] == "service_preview"
    assert "external_preview" in explains[0].payload["assumptions"]
    assert "snapshot_id" not in explains[0].payload


def test_route_snapshot_falls_back_to_local_navigator_when_preview_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Tuple[Session, sessionmaker],
) -> None:
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")

    def _raise(self, payload):
        raise RuntimeError("logistics_service_unreachable")

    monkeypatch.setattr(
        "app.services.logistics.navigator.explain.LogisticsServiceClient.preview_route",
        _raise,
    )

    db, _ = db_session
    order = _seed_order(db)
    route = routes.create_route(db, order_id=str(order.id), distance_km=12.0, planned_duration_minutes=30)
    routes.upsert_stops(
        db,
        route_id=str(route.id),
        stops=[
            LogisticsStopIn(
                sequence=0,
                stop_type=logistics_models.LogisticsStopType.START,
                name="Start",
                lat=55.75,
                lon=37.6,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
            LogisticsStopIn(
                sequence=1,
                stop_type=logistics_models.LogisticsStopType.END,
                name="End",
                lat=55.76,
                lon=37.61,
                status=logistics_models.LogisticsStopStatus.PENDING,
            ),
        ],
    )

    snapshot = repository.get_latest_route_snapshot(db, route_id=str(route.id))
    assert snapshot is not None
    assert snapshot.provider == "noop"
    assert snapshot.distance_km > 0

    explains = repository.list_navigator_explains(
        db,
        route_snapshot_id=str(snapshot.id),
        explain_type=logistics_models.LogisticsNavigatorExplainType.ETA,
    )
    assert len(explains) == 1
    assert explains[0].payload["navigator"] == "noop"
    assert explains[0].payload["method"] == "straight_line"
    assert "preview_fallback=logistics_service_unreachable" in explains[0].payload["assumptions"]


def test_eta_stable_for_same_input():
    adapter = navigator.get("noop")
    route = adapter.build_route(
        [
            navigator.GeoPoint(lat=55.75, lon=37.6),
            navigator.GeoPoint(lat=55.76, lon=37.61),
        ]
    )
    eta_first = adapter.estimate_eta(route).eta_minutes
    eta_second = adapter.estimate_eta(route).eta_minutes
    assert eta_first == eta_second


def test_deviation_score_deterministic():
    adapter = navigator.get("noop")
    route = adapter.build_route(
        [
            navigator.GeoPoint(lat=55.75, lon=37.6),
            navigator.GeoPoint(lat=55.76, lon=37.61),
        ]
    )
    actual_points = [
        navigator.GeoPoint(lat=55.75, lon=37.6),
        navigator.GeoPoint(lat=55.77, lon=37.7),
    ]
    score_first = adapter.deviation_score(route, actual_points)
    score_second = adapter.deviation_score(route, actual_points)
    assert score_first == score_second


def test_registered_navigator_providers_are_local_only():
    assert registry.registered_provider_names() == ("noop", "osm_stub", "yandex_stub")
    assert "yandex" not in registry.registered_provider_names()
    assert "osm" not in registry.registered_provider_names()
    assert registry.can_replay_locally("osrm") is False
    assert registry.get_local_evidence_adapter("osrm").provider == "noop"


@pytest.mark.parametrize("provider", ["yandex", "osm"])
def test_real_named_navigator_providers_do_not_resolve_to_stubs(provider: str):
    with pytest.raises(ValueError, match=f"logistics_navigator_provider_unconfigured:{provider}"):
        registry.get(provider)


@pytest.mark.parametrize("stub_provider", ["yandex_stub", "osm_stub"])
def test_explicit_stub_navigator_provider_is_labeled_as_stub(monkeypatch, stub_provider: str):
    monkeypatch.setattr(registry.settings, "APP_ENV", "dev")
    adapter = registry.get(stub_provider)
    route = adapter.build_route(
        [
            navigator.GeoPoint(lat=55.75, lon=37.6),
            navigator.GeoPoint(lat=55.76, lon=37.61),
        ]
    )
    eta = adapter.estimate_eta(route)

    assert route.provider == stub_provider
    assert f"stub_provider={stub_provider}" in eta.assumptions
    assert eta.method == "stub_straight_line"


@pytest.mark.parametrize("stub_provider", ["yandex_stub", "osm_stub"])
def test_explicit_stub_navigator_provider_is_blocked_in_prod(monkeypatch, stub_provider: str):
    monkeypatch.setattr(registry.settings, "APP_ENV", "prod")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS_IN_PROD", raising=False)

    with pytest.raises(ValueError, match=f"logistics_navigator_stub_not_allowed:{stub_provider}"):
        registry.get(stub_provider)

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Tuple

import pytest
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models import logistics as logistics_models
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics import deviation, eta, routes
from app.services.logistics.orders import create_order
from app.services.logistics.service_client import ETAResult, DeviationResult as ServiceDeviationResult
from app.tests._logistics_route_harness import logistics_session_context


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    with logistics_session_context() as ctx:
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
        full_name="Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return str(vehicle.id), str(driver.id)


def test_eta_uses_logistics_service(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
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
            explain={"primary_reason": "NORMAL_TRAFFIC"},
        ),
    )

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.TRIP,
        status=logistics_models.LogisticsOrderStatus.PLANNED,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        planned_end_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    route = routes.create_route(db, order_id=str(order.id), distance_km=10.0, planned_duration_minutes=30)
    routes.activate_route(db, route_id=str(route.id))
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

    snapshot = eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")
    assert snapshot is not None
    assert snapshot.eta_confidence == 88
    assert snapshot.inputs["provider"] == "osrm"
    assert snapshot.inputs["service_eta_minutes"] == 45
    assert snapshot.inputs["service_explain"]["primary_reason"] == "NORMAL_TRAFFIC"


def test_eta_fallback_when_disabled(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=False),
    )

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    planned_end = datetime.now(timezone.utc) + timedelta(hours=2)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.TRIP,
        status=logistics_models.LogisticsOrderStatus.PLANNED,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        planned_end_at=planned_end,
    )

    snapshot = eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")
    assert snapshot is not None
    assert snapshot.method == logistics_models.LogisticsETAMethod.PLANNED
    assert snapshot.eta_end_at.isoformat().startswith(planned_end.isoformat()[:19])


def test_deviation_uses_logistics_service(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")
    monkeypatch.setattr(
        "app.services.logistics.deviation.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=True),
    )
    monkeypatch.setattr(
        "app.services.logistics.deviation.LogisticsServiceClient.compute_deviation",
        lambda self, payload: ServiceDeviationResult(
            deviation_meters=1200,
            is_violation=True,
            confidence=0.9,
            explain={"primary_reason": "ROUTE_DEVIATION"},
        ),
    )

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.TRIP,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
    )
    route = routes.create_route(db, order_id=str(order.id), distance_km=10.0, planned_duration_minutes=30)
    routes.activate_route(db, route_id=str(route.id))
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

    result = deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        lat=56.0,
        lon=38.0,
        ts=datetime.now(timezone.utc),
    )
    assert result.event is not None
    assert result.risk_signal is not None
    assert result.event.explain["primary_reason"] == "ROUTE_DEVIATION"

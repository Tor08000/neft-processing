import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Tuple

import pytest
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models import logistics as logistics_models
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.logistics import LogisticsDeviationEvent
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics.defaults import OFF_ROUTE_DEFAULTS
from app.services.logistics import deviation, routes
from app.services.logistics.orders import create_order
from app.tests._logistics_route_harness import logistics_session_context


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    with logistics_session_context() as ctx:
        yield ctx


def _seed_fleet(db: Session) -> Tuple[str, str]:
    vehicle = FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="DEV123",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Deviation Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return str(vehicle.id), str(driver.id)


def _list_deviation_events(db: Session, *, order_id: str) -> list[LogisticsDeviationEvent]:
    return (
        db.query(LogisticsDeviationEvent)
        .filter(LogisticsDeviationEvent.order_id == order_id)
        .order_by(LogisticsDeviationEvent.ts.asc(), LogisticsDeviationEvent.created_at.asc())
        .all()
    )


def test_deviation_events(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.setattr(
        "app.services.logistics.deviation.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=False),
    )
    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)

    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.DELIVERY,
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

    base_ts = datetime.now(timezone.utc)
    first = deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        ts=base_ts,
        lat=55.7505,
        lon=37.6005,
    )
    assert first.event is None
    assert _list_deviation_events(db, order_id=str(order.id)) == []

    for idx in range(OFF_ROUTE_DEFAULTS.off_route_consecutive_points):
        deviation.check_route_deviation(
            db,
            order=order,
            route=route,
            ts=base_ts + timedelta(minutes=5 + idx * 8),
            lat=56.5,
            lon=38.0,
        )
    deviations = _list_deviation_events(db, order_id=str(order.id))
    assert deviations and deviations[0].event_type.value == "OFF_ROUTE"

    deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        ts=base_ts + timedelta(minutes=30),
        lat=55.7508,
        lon=37.6008,
    )
    deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        ts=base_ts + timedelta(minutes=32),
        lat=55.7509,
        lon=37.6009,
    )
    deviations = _list_deviation_events(db, order_id=str(order.id))
    assert any(event.event_type.value == "BACK_ON_ROUTE" for event in deviations)


def test_deviation_state_machine_out_of_order(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Tuple[Session, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.setattr(
        "app.services.logistics.deviation.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=False),
    )
    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.DELIVERY,
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
    base_ts = datetime.now(timezone.utc)
    for idx in range(OFF_ROUTE_DEFAULTS.off_route_consecutive_points):
        deviation.check_route_deviation(
            db,
            order=order,
            route=route,
            ts=base_ts + timedelta(minutes=5 + idx * 6),
            lat=56.5,
            lon=38.0,
        )
    deviations = _list_deviation_events(db, order_id=str(order.id))
    assert any(event.event_type.value == "OFF_ROUTE" for event in deviations)

    older = deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        ts=base_ts - timedelta(minutes=1),
        lat=56.5,
        lon=38.0,
    )
    assert older.event is None
    deviations_after = _list_deviation_events(db, order_id=str(order.id))
    assert len(deviations_after) == len(deviations)

    duplicate = deviation.check_route_deviation(
        db,
        order=order,
        route=route,
        ts=base_ts + timedelta(minutes=5 + (OFF_ROUTE_DEFAULTS.off_route_consecutive_points - 1) * 6),
        lat=56.5,
        lon=38.0,
    )
    assert duplicate.event is None
    deviations_dup = _list_deviation_events(db, order_id=str(order.id))
    assert len(deviations_dup) == len(deviations)

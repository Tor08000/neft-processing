import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.db import Base
from app.models import logistics as logistics_models
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.schemas.logistics import LogisticsStopIn, LogisticsTrackingEventIn
from app.services.logistics.defaults import OFF_ROUTE_DEFAULTS
from app.services.logistics import repository, routes, tracking
from app.services.logistics.orders import create_order


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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


def test_deviation_events(db_session: Tuple[Session, sessionmaker]):
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
    tracking.ingest_tracking_event(
        db,
        order_id=str(order.id),
        payload=LogisticsTrackingEventIn(
            event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
            ts=base_ts,
            lat=55.7505,
            lon=37.6005,
            speed_kmh=40.0,
        ),
    )
    assert repository.list_deviation_events(db, order_id=str(order.id)) == []

    for idx in range(OFF_ROUTE_DEFAULTS.off_route_consecutive_points):
        tracking.ingest_tracking_event(
            db,
            order_id=str(order.id),
            payload=LogisticsTrackingEventIn(
                event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
                ts=base_ts + timedelta(minutes=5 + idx * 8),
                lat=56.5,
                lon=38.0,
                speed_kmh=50.0,
            ),
        )
    deviations = repository.list_deviation_events(db, order_id=str(order.id))
    assert deviations and deviations[0].event_type.value == "OFF_ROUTE"

    tracking.ingest_tracking_event(
        db,
        order_id=str(order.id),
        payload=LogisticsTrackingEventIn(
            event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
            ts=base_ts + timedelta(minutes=30),
            lat=55.7508,
            lon=37.6008,
            speed_kmh=30.0,
        ),
    )
    tracking.ingest_tracking_event(
        db,
        order_id=str(order.id),
        payload=LogisticsTrackingEventIn(
            event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
            ts=base_ts + timedelta(minutes=32),
            lat=55.7509,
            lon=37.6009,
            speed_kmh=30.0,
        ),
    )
    deviations = repository.list_deviation_events(db, order_id=str(order.id))
    assert any(event.event_type.value == "BACK_ON_ROUTE" for event in deviations)


def test_deviation_state_machine_out_of_order(db_session: Tuple[Session, sessionmaker]):
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
        tracking.ingest_tracking_event(
            db,
            order_id=str(order.id),
            payload=LogisticsTrackingEventIn(
                event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
                ts=base_ts + timedelta(minutes=5 + idx * 6),
                lat=56.5,
                lon=38.0,
                speed_kmh=50.0,
            ),
        )
    deviations = repository.list_deviation_events(db, order_id=str(order.id))
    assert any(event.event_type.value == "OFF_ROUTE" for event in deviations)

    tracking.ingest_tracking_event(
        db,
        order_id=str(order.id),
        payload=LogisticsTrackingEventIn(
            event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
            ts=base_ts - timedelta(minutes=1),
            lat=56.5,
            lon=38.0,
            speed_kmh=50.0,
        ),
    )
    deviations_after = repository.list_deviation_events(db, order_id=str(order.id))
    assert len(deviations_after) == len(deviations)

    tracking.ingest_tracking_event(
        db,
        order_id=str(order.id),
        payload=LogisticsTrackingEventIn(
            event_type=logistics_models.LogisticsTrackingEventType.LOCATION,
            ts=base_ts + timedelta(minutes=5 + (OFF_ROUTE_DEFAULTS.off_route_consecutive_points - 1) * 6),
            lat=56.5,
            lon=38.0,
            speed_kmh=50.0,
        ),
    )
    deviations_dup = repository.list_deviation_events(db, order_id=str(order.id))
    assert len(deviations_dup) == len(deviations)

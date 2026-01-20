import os
from typing import Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.db import Base
from app.models import fleet as fleet_models
from app.models import logistics as logistics_models
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics import navigator, repository, routes
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

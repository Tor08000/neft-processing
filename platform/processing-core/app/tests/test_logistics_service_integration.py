import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.db import Base
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics import deviation, eta, routes
from app.services.logistics.orders import create_order
from app.services.logistics.service_client import httpx as service_httpx


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


class DummyClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, json):
        return self.response


def test_eta_uses_logistics_service(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")

    response = httpx.Response(
        200,
        json={
            "eta_minutes": 45,
            "confidence": 0.88,
            "provider": "mock",
            "explain": {"primary_reason": "NORMAL_TRAFFIC"},
        },
    )
    monkeypatch.setattr(service_httpx, "Client", lambda *args, **kwargs: DummyClient(response))

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=models.LogisticsOrderType.TRIP,
        status=models.LogisticsOrderStatus.PLANNED,
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
                stop_type=models.LogisticsStopType.START,
                name="Start",
                lat=55.75,
                lon=37.6,
                status=models.LogisticsStopStatus.PENDING,
            ),
            LogisticsStopIn(
                sequence=1,
                stop_type=models.LogisticsStopType.END,
                name="End",
                lat=55.76,
                lon=37.61,
                status=models.LogisticsStopStatus.PENDING,
            ),
        ],
    )

    snapshot = eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")
    assert snapshot is not None
    assert snapshot.eta_confidence == 88
    assert snapshot.inputs["provider"] == "mock"
    assert snapshot.inputs["service_eta_minutes"] == 45
    assert snapshot.inputs["service_explain"]["primary_reason"] == "NORMAL_TRAFFIC"


def test_eta_fallback_when_disabled(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    planned_end = datetime.now(timezone.utc) + timedelta(hours=2)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=models.LogisticsOrderType.TRIP,
        status=models.LogisticsOrderStatus.PLANNED,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        planned_end_at=planned_end,
    )

    snapshot = eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")
    assert snapshot is not None
    assert snapshot.method == models.LogisticsETAMethod.PLANNED
    assert snapshot.eta_end_at.isoformat().startswith(planned_end.isoformat()[:19])


def test_deviation_uses_logistics_service(monkeypatch: pytest.MonkeyPatch, db_session: Tuple[Session, sessionmaker]):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "1")

    response = httpx.Response(
        200,
        json={
            "deviation_meters": 1200,
            "is_violation": True,
            "confidence": 0.9,
            "explain": {"primary_reason": "ROUTE_DEVIATION"},
        },
    )
    monkeypatch.setattr(service_httpx, "Client", lambda *args, **kwargs: DummyClient(response))

    db, _ = db_session
    vehicle_id, driver_id = _seed_fleet(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=models.LogisticsOrderType.TRIP,
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
                stop_type=models.LogisticsStopType.START,
                name="Start",
                lat=55.75,
                lon=37.6,
                status=models.LogisticsStopStatus.PENDING,
            ),
            LogisticsStopIn(
                sequence=1,
                stop_type=models.LogisticsStopType.END,
                name="End",
                lat=55.76,
                lon=37.61,
                status=models.LogisticsStopStatus.PENDING,
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


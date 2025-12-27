import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.api.v1.endpoints.logistics import router as logistics_router
from app.db import Base, get_db
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus


@pytest.fixture()
def logistics_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(logistics_router, prefix="")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal

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

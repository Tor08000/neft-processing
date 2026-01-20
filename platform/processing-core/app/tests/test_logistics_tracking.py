import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

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

    app = FastAPI(generate_unique_id_function=generate_unique_id)
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
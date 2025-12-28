import os
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
        plate_number="A777AA",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Route Driver",
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


def test_routes_and_stops(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    order_id = _create_order(client, vehicle_id, driver_id)

    route_resp = client.post(
        f"/api/v1/logistics/orders/{order_id}/routes",
        json={"distance_km": 120.5, "planned_duration_minutes": 180},
    )
    assert route_resp.status_code == 200
    route_id = route_resp.json()["id"]
    assert route_resp.json()["version"] == 1

    stops_payload = [
        {
            "sequence": 0,
            "stop_type": "START",
            "name": "Warehouse",
            "status": "PENDING",
        },
        {
            "sequence": 1,
            "stop_type": "DELIVERY",
            "name": "Client",
            "status": "PENDING",
        },
    ]
    stops_resp = client.post(f"/api/v1/logistics/routes/{route_id}/stops", json=stops_payload)
    assert stops_resp.status_code == 200
    assert len(stops_resp.json()) == 2

    activate_resp = client.post(f"/api/v1/logistics/routes/{route_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "ACTIVE"

    updated_payload = [
        {
            "id": stops_resp.json()[0]["id"],
            "sequence": 0,
            "stop_type": "START",
            "name": "Warehouse",
            "status": "ARRIVED",
        }
    ]
    updated_resp = client.post(f"/api/v1/logistics/routes/{route_id}/stops", json=updated_payload)
    assert updated_resp.status_code == 200
    assert updated_resp.json()[0]["status"] == "ARRIVED"

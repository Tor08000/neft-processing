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
        plate_number="A123AA",
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Test Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)
    return str(vehicle.id), str(driver.id)


def test_order_lifecycle(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client

    with SessionLocal() as db:
        vehicle_id, driver_id = _seed_fleet(db)

    payload = {
        "tenant_id": 1,
        "client_id": "client-1",
        "order_type": "DELIVERY",
        "vehicle_id": vehicle_id,
        "driver_id": driver_id,
    }
    create_resp = client.post("/api/v1/logistics/orders", json=payload)
    assert create_resp.status_code == 200
    order_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "DRAFT"

    start_resp = client.post(f"/api/v1/logistics/orders/{order_id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"
    assert start_resp.json()["actual_start_at"] is not None

    complete_resp = client.post(f"/api/v1/logistics/orders/{order_id}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "COMPLETED"
    assert complete_resp.json()["actual_end_at"] is not None

    cancel_resp = client.post("/api/v1/logistics/orders", json=payload)
    assert cancel_resp.status_code == 200
    cancel_id = cancel_resp.json()["id"]
    cancel_order = client.post(f"/api/v1/logistics/orders/{cancel_id}/cancel")
    assert cancel_order.status_code == 200
    assert cancel_order.json()["status"] == "CANCELLED"

from __future__ import annotations

import os
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation
from app.routers.admin.fuel import router as admin_fuel_router
from app.services.admin_auth import require_admin


@pytest.fixture()
def admin_fuel_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(admin_fuel_router, prefix="/api/v1/admin")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = lambda: {
        "user_id": "admin-1",
        "email": "admin@example.com",
        "roles": ["SUPERADMIN"],
    }

    with TestClient(app) as client:
        yield client, testing_session_local

    FuelStation.__table__.drop(bind=engine)
    FuelNetwork.__table__.drop(bind=engine)
    engine.dispose()


def test_patch_station_risk_zone_updates_fields(admin_fuel_client: Tuple[TestClient, sessionmaker]) -> None:
    client, session_local = admin_fuel_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(
            network_id=str(network.id),
            station_code="S1",
            name="S1",
            city="Moscow",
            lat=55.751,
            lon=37.611,
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        station_id = str(station.id)

    response = client.patch(
        f"/api/v1/admin/fuel/stations/{station_id}/risk-zone",
        json={"risk_zone": "RED", "reason": "Chargeback cluster"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_zone"] == "RED"
    assert payload["risk_zone_reason"] == "Chargeback cluster"
    assert payload["risk_zone_updated_by"] == "admin-1"
    assert payload["risk_zone_updated_at"] is not None


def test_patch_station_risk_zone_requires_reason_for_red(admin_fuel_client: Tuple[TestClient, sessionmaker]) -> None:
    client, session_local = admin_fuel_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(
            network_id=str(network.id),
            station_code="S2",
            name="S2",
            city="Moscow",
            lat=55.751,
            lon=37.611,
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)

    response = client.patch(
        f"/api/v1/admin/fuel/stations/{station.id}/risk-zone",
        json={"risk_zone": "RED"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "reason_required_for_red_zone"


def test_patch_station_health_updates_fields(admin_fuel_client: Tuple[TestClient, sessionmaker]) -> None:
    client, session_local = admin_fuel_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(
            network_id=str(network.id),
            station_code="S3",
            name="S3",
            city="Moscow",
            lat=55.751,
            lon=37.611,
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)

    response = client.patch(
        f"/api/v1/admin/fuel/stations/{station.id}/health",
        json={"health_status": "DEGRADED", "reason": "POS timeout", "source": "MANUAL"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["health_status"] == "DEGRADED"
    assert body["health_reason"] == "POS timeout"

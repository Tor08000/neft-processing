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
from app.routers.internal.fuel_stations import router as internal_fuel_stations_router


@pytest.fixture()
def internal_fuel_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(internal_fuel_stations_router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, testing_session_local

    FuelStation.__table__.drop(bind=engine)
    FuelNetwork.__table__.drop(bind=engine)
    engine.dispose()


def test_heartbeat_updates_station_health(internal_fuel_client: Tuple[TestClient, sessionmaker]) -> None:
    client, session_local = internal_fuel_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(
            network_id=str(network.id),
            station_code="S-HB",
            name="Heartbeat",
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)

    response = client.post(
        f"/api/v1/internal/fuel/stations/{station.id}/heartbeat",
        json={"status": "ONLINE", "source": "TERMINAL", "terminal_id": "pos-123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["health_status"] == "ONLINE"
    assert payload["last_heartbeat"] is not None

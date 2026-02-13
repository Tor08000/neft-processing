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

from app.api.v1.endpoints.fuel_stations import router as fuel_stations_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation
from app.services.fuel.stations import haversine_km


@pytest.fixture()
def fuel_stations_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(fuel_stations_router, prefix="")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    FuelStation.__table__.drop(bind=engine)
    FuelNetwork.__table__.drop(bind=engine)
    engine.dispose()


def test_haversine_same_point_is_zero() -> None:
    assert haversine_km(55.7558, 37.6176, 55.7558, 37.6176) == pytest.approx(0.0, abs=1e-9)


def test_haversine_moscow_to_spb_in_expected_range() -> None:
    distance = haversine_km(55.7558, 37.6176, 59.9343, 30.3351)
    assert 600.0 <= distance <= 700.0


def test_nearest_endpoint_returns_sorted_items_within_radius(fuel_stations_client: Tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = fuel_stations_client

    with SessionLocal() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        db.add_all(
            [
                FuelStation(
                    network_id=str(network.id),
                    station_code="M1",
                    name="Moscow Center",
                    city="Moscow",
                    lat=55.7558,
                    lon=37.6176,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="M2",
                    name="Moscow West",
                    city="Moscow",
                    lat=55.7512,
                    lon=37.5845,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="FAR",
                    name="Far away",
                    city="Moscow",
                    lat=55.85,
                    lon=37.95,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/fuel/stations/nearest",
        params={"lat": 55.7558, "lon": 37.6176, "radius_km": 5, "limit": 30},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    assert data["meta"]["returned"] == len(data["items"])

    distances = [item["distance_km"] for item in data["items"]]
    assert all(distance <= 5 for distance in distances)
    assert distances == sorted(distances)
    assert all("distance_km" in item for item in data["items"])

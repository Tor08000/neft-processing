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
from app.services.fuel.stations import build_nav_url, haversine_km


@pytest.fixture()
def fuel_stations_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(fuel_stations_router, prefix="")

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


def test_haversine_same_point_is_zero() -> None:
    assert haversine_km(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_moscow_to_spb_in_expected_range() -> None:
    distance = haversine_km(55.7558, 37.6173, 59.9311, 30.3609)
    assert 600.0 <= distance <= 800.0


def test_haversine_is_symmetric() -> None:
    distance_ab = haversine_km(55.7558, 37.6173, 59.9311, 30.3609)
    distance_ba = haversine_km(59.9311, 30.3609, 55.7558, 37.6173)
    assert distance_ab == pytest.approx(distance_ba)


def test_nearest_endpoint_returns_deterministic_order_for_seeded_stations(
    fuel_stations_client: Tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = fuel_stations_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        db.add_all(
            [
                FuelStation(
                    network_id=str(network.id),
                    station_code="S1",
                    name="S1",
                    city="Moscow",
                    lat=55.7510,
                    lon=37.6110,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="S2",
                    name="S2",
                    city="Moscow",
                    lat=55.7600,
                    lon=37.6200,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="S3",
                    name="S3",
                    city="Moscow",
                    lat=55.7700,
                    lon=37.6300,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="S4",
                    name="S4",
                    city="Moscow",
                    lat=55.7900,
                    lon=37.6500,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
                FuelStation(
                    network_id=str(network.id),
                    station_code="S5",
                    name="S5",
                    city="Moscow",
                    lat=55.8200,
                    lon=37.6900,
                    status=fuel_models.FuelStationStatus.ACTIVE,
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/fuel/stations/nearest",
        params={"lat": 55.7500, "lon": 37.6100, "radius_km": 50, "limit": 10},
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) == 5
    assert data["meta"]["returned"] == 5

    distances = [item["distance_km"] for item in data["items"]]
    assert all("distance_km" in item for item in data["items"])
    assert distances == sorted(distances)
    assert all(distance <= 50 for distance in distances)

    ordered_station_codes = [item["station_code"] for item in data["items"]]
    assert ordered_station_codes == ["S1", "S2", "S3", "S4", "S5"]


def test_nearest_and_detail_include_risk_zone_fields(
    fuel_stations_client: Tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = fuel_stations_client

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(
            network_id=str(network.id),
            station_code="S-RISK",
            name="Risky",
            lat=55.7510,
            lon=37.6110,
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="RED",
            risk_zone_reason="Suspicious POS pattern",
            risk_zone_updated_by="admin@example.com",
        )
        db.add(station)
        db.commit()
        db.refresh(station)

    nearest = client.get(
        "/api/v1/fuel/stations/nearest",
        params={"lat": 55.7500, "lon": 37.6100, "radius_km": 50, "limit": 10},
    )
    assert nearest.status_code == 200
    nearest_item = nearest.json()["items"][0]
    assert nearest_item["risk_zone"] == "RED"
    assert nearest_item["risk_zone_reason"] == "Suspicious POS pattern"

    detail = client.get(f"/api/v1/fuel/stations/{station.id}")
    assert detail.status_code == 200
    detail_json = detail.json()
    assert detail_json["risk_zone"] == "RED"
    assert detail_json["risk_zone_reason"] == "Suspicious POS pattern"


def test_build_nav_url_google_with_destination() -> None:
    nav_url = build_nav_url(55.75, 37.62, provider="google")
    assert nav_url is not None
    assert "google.com/maps/dir" in nav_url
    assert "destination=55.75%2C37.62" in nav_url


def test_build_nav_url_returns_none_without_coordinates() -> None:
    assert build_nav_url(None, 37.62, provider="google") is None
    assert build_nav_url(55.75, None, provider="google") is None


def test_build_nav_url_yandex_with_from_coordinates() -> None:
    nav_url = build_nav_url(55.75, 37.62, provider="yandex", from_lat=55.7, from_lon=37.5)
    assert nav_url is not None
    assert "yandex.ru/maps" in nav_url
    assert "rtext=55.7%2C37.5~55.75%2C37.62" in nav_url

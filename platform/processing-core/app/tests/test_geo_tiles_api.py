from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.api.v1.endpoints.geo_tiles import router as geo_tiles_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation
from app.models.geo_metrics import GeoStationMetricsDaily
from app.services.geo_analytics import mercator_tile_xy


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    GeoStationMetricsDaily.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(geo_tiles_router, prefix="")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    return client, testing_session_local


def test_mercator_tile_xy_same_coords_same_tile_and_clamp() -> None:
    assert mercator_tile_xy(55.75, 37.61, 10) == mercator_tile_xy(55.75, 37.61, 10)

    tile_high_lat = mercator_tile_xy(89.0, 37.61, 10)
    tile_clamped = mercator_tile_xy(85.0511, 37.61, 10)
    assert tile_high_lat == tile_clamped


def test_mercator_tile_xy_different_coords_different_tiles() -> None:
    tile_moscow = mercator_tile_xy(55.75, 37.61, 10)
    tile_spb = mercator_tile_xy(59.93, 30.31, 10)
    assert tile_moscow != tile_spb


def test_geo_tiles_bbox_filter_and_aggregation() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="GN2", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        inside_1 = FuelStation(network_id=str(network.id), station_code="A", name="A", city="C", lat=55.75, lon=37.61, status=fuel_models.FuelStationStatus.ACTIVE)
        inside_2 = FuelStation(network_id=str(network.id), station_code="B", name="B", city="C", lat=55.76, lon=37.62, status=fuel_models.FuelStationStatus.ACTIVE)
        outside = FuelStation(network_id=str(network.id), station_code="C", name="C", city="C", lat=60.0, lon=30.0, status=fuel_models.FuelStationStatus.ACTIVE)
        db.add_all([inside_1, inside_2, outside])
        db.commit()
        db.refresh(inside_1)
        db.refresh(inside_2)
        db.refresh(outside)

        db.add_all(
            [
                GeoStationMetricsDaily(day=date(2026, 2, 12), station_id=str(inside_1.id), tx_count=5, captured_count=4, declined_count=1, amount_sum=Decimal("100.00"), liters_sum=Decimal("20.000"), risk_red_count=1, risk_yellow_count=2),
                GeoStationMetricsDaily(day=date(2026, 2, 12), station_id=str(inside_2.id), tx_count=7, captured_count=6, declined_count=1, amount_sum=Decimal("200.00"), liters_sum=Decimal("25.000"), risk_red_count=0, risk_yellow_count=1),
                GeoStationMetricsDaily(day=date(2026, 2, 12), station_id=str(outside.id), tx_count=100, captured_count=90, declined_count=10, amount_sum=Decimal("9999.00"), liters_sum=Decimal("500.000"), risk_red_count=5, risk_yellow_count=5),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/geo/tiles?date_from=2026-02-12&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&zoom=10&metric=tx_count&limit_tiles=2000"
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["returned_tiles"] == 2
    assert sum(item["value"] for item in payload["items"]) == 12
    assert "tile_x" in payload["items"][0]
    assert "tile_y" in payload["items"][0]


def test_geo_tiles_metric_selection_changes_values() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="GN3", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        station = FuelStation(network_id=str(network.id), station_code="A", name="A", city="C", lat=55.75, lon=37.61, status=fuel_models.FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)

        db.add(
            GeoStationMetricsDaily(
                day=date(2026, 2, 12),
                station_id=str(station.id),
                tx_count=3,
                captured_count=3,
                declined_count=0,
                amount_sum=Decimal("123.45"),
                liters_sum=Decimal("10.000"),
                risk_red_count=0,
                risk_yellow_count=1,
            )
        )
        db.commit()

    base_qs = "date_from=2026-02-12&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&zoom=10&limit_tiles=2000"
    tx_response = client.get(f"/api/v1/geo/tiles?{base_qs}&metric=tx_count")
    amount_response = client.get(f"/api/v1/geo/tiles?{base_qs}&metric=amount_sum")

    assert tx_response.status_code == 200
    assert amount_response.status_code == 200

    tx_value = tx_response.json()["items"][0]["value"]
    amount_value = amount_response.json()["items"][0]["value"]

    assert tx_value == 3
    assert amount_value == 123.45
    assert tx_value != amount_value

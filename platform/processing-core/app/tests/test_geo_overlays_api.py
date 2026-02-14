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

from app.api.v1.endpoints.geo_metrics import router as geo_metrics_router
from app.api.v1.endpoints.geo_tiles import router as geo_tiles_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation
from app.models.geo_metrics import GeoStationMetricsDaily, GeoTilesDailyOverlay
from app.services.geo_analytics import build_geo_overlay_tiles_for_day


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    GeoStationMetricsDaily.__table__.create(bind=engine)
    GeoTilesDailyOverlay.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(geo_tiles_router, prefix="")
    app.include_router(geo_metrics_router, prefix="")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


def test_build_geo_overlay_tiles_for_day() -> None:
    _, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(
            name="NET", provider_code="GN4", status=fuel_models.FuelNetworkStatus.ACTIVE
        )
        db.add(network)
        db.commit()
        db.refresh(network)

        station_1 = FuelStation(
            network_id=str(network.id),
            station_code="AA",
            name="AA",
            city="C",
            lat=55.75,
            lon=37.61,
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="OFFLINE",
            risk_zone="RED",
        )
        station_2 = FuelStation(
            network_id=str(network.id),
            station_code="BB",
            name="BB",
            city="C",
            lat=55.751,
            lon=37.611,
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="DEGRADED",
            risk_zone="YELLOW",
        )
        db.add_all([station_1, station_2])
        db.commit()
        db.refresh(station_1)
        db.refresh(station_2)

        db.add_all(
            [
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(station_1.id),
                    risk_red_count=2,
                    amount_sum=Decimal("10.00"),
                ),
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(station_2.id),
                    risk_red_count=1,
                    amount_sum=Decimal("20.00"),
                ),
            ]
        )
        db.commit()

        built = build_geo_overlay_tiles_for_day(db, day=date(2026, 2, 12), zoom=10)
        assert built >= 3

        rows = (
            db.query(GeoTilesDailyOverlay)
            .filter(
                GeoTilesDailyOverlay.day == date(2026, 2, 12),
                GeoTilesDailyOverlay.zoom == 10,
            )
            .all()
        )
        by_kind = {row.overlay_kind: row.value for row in rows}
        assert by_kind["RISK_RED"] == 3
        assert by_kind["HEALTH_OFFLINE"] == 1
        assert by_kind["HEALTH_DEGRADED"] == 1


def test_geo_tiles_overlays_endpoint_sums_range() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        db.add_all(
            [
                GeoTilesDailyOverlay(
                    day=date(2026, 2, 11),
                    zoom=10,
                    tile_x=619,
                    tile_y=320,
                    overlay_kind="HEALTH_OFFLINE",
                    value=2,
                ),
                GeoTilesDailyOverlay(
                    day=date(2026, 2, 12),
                    zoom=10,
                    tile_x=619,
                    tile_y=320,
                    overlay_kind="HEALTH_OFFLINE",
                    value=3,
                ),
                GeoTilesDailyOverlay(
                    day=date(2026, 2, 12),
                    zoom=10,
                    tile_x=100,
                    tile_y=100,
                    overlay_kind="HEALTH_OFFLINE",
                    value=99,
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/geo/tiles/overlays?date_from=2026-02-11&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&zoom=10&overlay_kind=HEALTH_OFFLINE&limit_tiles=2000"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_tiles"] == 1
    assert payload["items"][0]["value"] == 5


def test_geo_stations_overlay_endpoint_bbox_metric_and_filters() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(
            name="NET", provider_code="GN4", status=fuel_models.FuelNetworkStatus.ACTIVE
        )
        db.add(network)
        db.commit()
        db.refresh(network)

        inside_1 = FuelStation(
            network_id=str(network.id),
            station_code="A1",
            name="A1",
            city="C",
            lat=55.75,
            lon=37.61,
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="OFFLINE",
            risk_zone="RED",
        )
        inside_2 = FuelStation(
            network_id=str(network.id),
            station_code="A2",
            name="A2",
            city="C",
            lat=55.755,
            lon=37.615,
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="ONLINE",
            risk_zone="GREEN",
        )
        outside = FuelStation(
            network_id=str(network.id),
            station_code="A3",
            name="A3",
            city="C",
            lat=59.93,
            lon=30.31,
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="OFFLINE",
            risk_zone="RED",
        )
        db.add_all([inside_1, inside_2, outside])
        db.commit()
        for station in (inside_1, inside_2, outside):
            db.refresh(station)

        db.add_all(
            [
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(inside_1.id),
                    tx_count=10,
                    risk_red_count=4,
                    amount_sum=Decimal("100.00"),
                ),
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(inside_2.id),
                    tx_count=7,
                    risk_red_count=1,
                    amount_sum=Decimal("70.00"),
                ),
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(outside.id),
                    tx_count=100,
                    risk_red_count=99,
                    amount_sum=Decimal("999.00"),
                ),
            ]
        )
        db.commit()

    response = client.get(
        f"/api/v1/geo/stations/overlay?date_from=2026-02-12&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&metric=tx_count&health_status=OFFLINE&risk_zone=RED&partner_id={network.id}&limit=500"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["returned"] == 1
    assert payload["items"][0]["name"] == "A1"
    assert payload["items"][0]["value"] == 10

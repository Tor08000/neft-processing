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

from app.api.v1.endpoints.geo_metrics import router as geo_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation
from app.models.geo_metrics import GeoStationMetricsDaily


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    GeoStationMetricsDaily.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(geo_router, prefix="")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    return client, testing_session_local


def test_geo_metrics_endpoint_sorted_by_amount_sum() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="GN2", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        s1 = FuelStation(network_id=str(network.id), station_code="A", name="A station", city="A city", lat=55.75, lon=37.61, status=fuel_models.FuelStationStatus.ACTIVE)
        s2 = FuelStation(network_id=str(network.id), station_code="B", name="B station", city="B city", lat=59.93, lon=30.31, status=fuel_models.FuelStationStatus.ACTIVE)
        db.add_all([s1, s2])
        db.commit()
        db.refresh(s1)
        db.refresh(s2)

        db.add_all(
            [
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(s1.id),
                    tx_count=5,
                    captured_count=4,
                    declined_count=1,
                    amount_sum=Decimal("1000.00"),
                    liters_sum=Decimal("20.000"),
                    risk_red_count=1,
                    risk_yellow_count=2,
                ),
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(s2.id),
                    tx_count=6,
                    captured_count=5,
                    declined_count=1,
                    amount_sum=Decimal("2000.00"),
                    liters_sum=Decimal("25.000"),
                    risk_red_count=0,
                    risk_yellow_count=1,
                ),
            ]
        )
        db.commit()

    response = client.get("/api/v1/geo/stations/metrics?date_from=2026-02-12&date_to=2026-02-12&metric=amount_sum&limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metric"] == "amount_sum"
    assert payload["limit"] == 20
    assert len(payload["items"]) == 2
    assert payload["items"][0]["station_id"] == str(s2.id)
    assert payload["items"][0]["amount_sum"] == 2000.0
    assert payload["items"][1]["station_id"] == str(s1.id)
    assert payload["items"][1]["station_name"] == "A station"

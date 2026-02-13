from __future__ import annotations

import io
import os
from typing import Tuple

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.api.dependencies.partner import partner_portal_user
from app.api.v1.endpoints.fuel_station_prices import router as fuel_station_prices_router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.audit_log import AuditLog
from app.models.fuel import FuelNetwork, FuelStation, FuelStationPrice


def _partner_token() -> dict:
    return {"user_id": "partner-user-1", "email": "partner@example.com", "partner_id": "p1", "tenant_id": 1}


def _make_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelStationPrice.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(fuel_station_prices_router, prefix="")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[partner_portal_user] = _partner_token

    client = TestClient(app)
    return client, testing_session_local


def test_put_then_get_station_prices_match() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(
            network_id=str(network.id),
            station_code="S1",
            name="S1",
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        station_id = str(station.id)

    put_response = client.put(
        f"/api/v1/partner/fuel/stations/{station_id}/prices",
        json={
            "source": "MANUAL",
            "items": [
                {"product_code": "AI95", "price": 56.10, "currency": "RUB"},
                {"product_code": "DT", "price": 63.40, "currency": "RUB"},
            ],
        },
    )
    assert put_response.status_code == 200

    get_response = client.get(f"/api/v1/fuel/stations/{station_id}/prices")
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["station_id"] == station_id
    prices = {item["product_code"]: item["price"] for item in payload["items"]}
    assert prices["AI95"] == 56.1
    assert prices["DT"] == 63.4


def test_import_csv_prices_returns_summary() -> None:
    client, session_local = _make_client()
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET2", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(
            network_id=str(network.id),
            station_code="S2",
            name="S2",
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        station_id = str(station.id)

    csv_data = "product_code,price,currency\nAI95,60.2,RUB\nAI92,55.1,RUB\n"
    response = client.post(
        f"/api/v1/partner/fuel/stations/{station_id}/prices/import",
        files={"file": ("prices.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 200
    summary = response.json()
    assert summary["inserted"] == 2
    assert summary["updated"] == 0
    assert summary["errors"] == []

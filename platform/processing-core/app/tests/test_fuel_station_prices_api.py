from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
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
from app.models.fuel import FuelNetwork, FuelStation, FuelStationPrice, FuelStationPriceAudit


def _partner_token() -> dict:
    return {"user_id": "partner-user-1", "email": "partner@example.com", "partner_id": "p1", "tenant_id": 1}


def _make_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelStationPrice.__table__.create(bind=engine)
    FuelStationPriceAudit.__table__.create(bind=engine)

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


def _seed_station(session_local: sessionmaker, code: str) -> str:
    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code=f"NET-{code}", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)
        station = FuelStation(
            network_id=str(network.id),
            station_code=code,
            name=code,
            status=fuel_models.FuelStationStatus.ACTIVE,
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        return str(station.id)


def test_put_then_get_station_prices_match() -> None:
    client, session_local = _make_client()
    station_id = _seed_station(session_local, "S1")

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
    assert payload["currency"] == "RUB"
    prices = {item["product_code"]: item["price"] for item in payload["items"]}
    assert prices["AI95"] == 56.1
    assert prices["DT"] == 63.4


def test_as_of_filtering_returns_active_window_only() -> None:
    client, session_local = _make_client()
    station_id = _seed_station(session_local, "S2")

    now = datetime.now(timezone.utc)
    past_from = (now - timedelta(days=3)).isoformat()
    past_to = (now - timedelta(days=1)).isoformat()
    current_from = (now - timedelta(hours=1)).isoformat()

    response = client.put(
        f"/api/v1/partner/fuel/stations/{station_id}/prices",
        json={
            "source": "MANUAL",
            "items": [
                {"product_code": "AI95", "price": 50.0, "currency": "RUB", "valid_from": past_from, "valid_to": past_to},
                {"product_code": "AI95", "price": 60.0, "currency": "RUB", "valid_from": current_from, "valid_to": None},
            ],
        },
    )
    assert response.status_code == 200

    active = client.get(f"/api/v1/fuel/stations/{station_id}/prices", params={"as_of": now.isoformat(), "product_code": "ai95"})
    assert active.status_code == 200
    items = active.json()["items"]
    assert len(items) == 1
    assert items[0]["price"] == 60.0


def test_import_csv_prices_returns_summary_with_errors() -> None:
    client, session_local = _make_client()
    station_id = _seed_station(session_local, "S3")

    csv_data = "product_code,price,currency\nAI95,60.2,RUB\nAI92,bad,RUB\n"
    response = client.post(
        f"/api/v1/partner/fuel/stations/{station_id}/prices/import",
        files={"file": ("prices.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 200
    summary = response.json()
    assert summary["station_id"] == station_id
    assert summary["inserted"] == 1
    assert summary["updated"] == 0
    assert len(summary["errors"]) == 1


def test_put_writes_price_audit_rows() -> None:
    client, session_local = _make_client()
    station_id = _seed_station(session_local, "S4")

    response = client.put(
        f"/api/v1/partner/fuel/stations/{station_id}/prices",
        headers={"X-Request-Id": "req-1"},
        json={"source": "MANUAL", "items": [{"product_code": "AI95", "price": 56.10, "currency": "RUB"}]},
    )
    assert response.status_code == 200

    with session_local() as db:
        rows = db.query(FuelStationPriceAudit).filter(FuelStationPriceAudit.station_id == station_id).all()
        assert rows
        assert rows[0].action == "UPSERT"
        assert rows[0].after is not None
        assert rows[0].request_id == "req-1"

from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base, get_db
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.routers.admin.explain import router as explain_router
from app.schemas.fuel import DeclineCode


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, sessionmaker]:
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
    app.include_router(explain_router, prefix="/api/v1/admin")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_fuel_refs(db: Session):
    network = FuelNetwork(id=str(uuid4()), name="Net", provider_code="NET", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(
        network_id=network.id,
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="RU",
        city="SPB",
        lat="0",
        lon="0",
        status=FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
    )
    db.add_all([network, station, card])
    db.commit()
    return card, station, network


def test_unified_explain_fuel_limit_decline(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        card, station, network = _seed_fuel_refs(db)
        limit_explain = {
            "applied_limit_id": str(uuid4()),
            "matched_on": ["fuel_type", "network"],
            "scope_type": "CLIENT",
            "scope_id": "client-1",
            "limit_type": "AMOUNT",
            "period": "DAILY",
            "limit": 10000,
            "used": 10000,
            "attempt": 2000,
            "remaining": 0,
            "time_window_start": "2025-01-01T00:00:00Z",
            "time_window_end": "2025-01-01T23:59:59Z",
            "timezone": "UTC",
        }
        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=None,
            driver_id=None,
            station_id=station.id,
            network_id=network.id,
            occurred_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            fuel_type="DIESEL",
            volume_ml=15000,
            unit_price_minor=500,
            amount_total_minor=7500,
            currency="RUB",
            status=FuelTransactionStatus.DECLINED,
            decline_code=DeclineCode.LIMIT_EXCEEDED_AMOUNT.value,
            meta={"limit_explain": limit_explain},
        )
        db.add(tx)
        db.commit()

    response = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sections"]["limits"]["applied_limit_id"] == limit_explain["applied_limit_id"]


def test_unified_explain_fuel_risk_decline(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        card, station, network = _seed_fuel_refs(db)
        risk_explain = {
            "decision": "DECLINE",
            "score": 95,
            "thresholds": {"block": 90},
            "policy": "fuel_v4",
            "factors": ["high_risk_station"],
            "decision_hash": "hash-1",
        }
        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=None,
            driver_id=None,
            station_id=station.id,
            network_id=network.id,
            occurred_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            fuel_type="DIESEL",
            volume_ml=15000,
            unit_price_minor=500,
            amount_total_minor=7500,
            currency="RUB",
            status=FuelTransactionStatus.DECLINED,
            decline_code=DeclineCode.RISK_BLOCK.value,
            meta={"risk_explain": risk_explain},
        )
        db.add(tx)
        db.commit()

    response = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sections"]["risk"]["decision"] == "DECLINE"

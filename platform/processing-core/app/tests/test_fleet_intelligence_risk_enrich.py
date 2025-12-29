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
from app.db import Base
from app.deps.db import get_db
from app.models.fleet import FleetDriver, FleetVehicle, FleetDriverStatus, FleetVehicleStatus
from app.models.fleet_intelligence import (
    DriverBehaviorLevel,
    FIDriverScore,
    FIStationTrustScore,
    FIVehicleEfficiencyScore,
    StationTrustLevel,
)
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus, FuelTransaction
from app.routers.admin.explain import router as explain_router
from app.services.fuel.risk_context import build_risk_context_for_fuel_tx


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def admin_client(admin_auth_headers: dict, db_session: Tuple[Session, sessionmaker]) -> Tuple[TestClient, sessionmaker]:
    _, SessionLocal = db_session
    app = FastAPI()
    app.include_router(explain_router, prefix="/api/v1/admin")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client, SessionLocal


def _seed_fleet_refs(db: Session):
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Fleet Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    vehicle = FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="VEH-1",
        status=FleetVehicleStatus.ACTIVE,
    )
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
        vehicle_id=vehicle.id,
        driver_id=driver.id,
    )
    db.add_all([driver, vehicle, network, station, card])
    db.commit()
    db.refresh(driver)
    db.refresh(vehicle)
    db.refresh(station)
    db.refresh(network)
    db.refresh(card)
    return driver, vehicle, station, network, card


def _seed_scores(db: Session, *, driver_id: str, vehicle_id: str, station_id: str, network_id: str):
    db.add(
        FIDriverScore(
            tenant_id=1,
            client_id="client-1",
            driver_id=driver_id,
            computed_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            window_days=7,
            score=70,
            level=DriverBehaviorLevel.HIGH,
            explain={"driver_behavior": {"score": 70}},
        )
    )
    db.add(
        FIVehicleEfficiencyScore(
            tenant_id=1,
            client_id="client-1",
            vehicle_id=vehicle_id,
            computed_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            window_days=7,
            efficiency_score=80,
            baseline_ml_per_100km=280.0,
            actual_ml_per_100km=300.0,
            delta_pct=0.0714,
            explain={"vehicle_efficiency": {"efficiency_score": 80}},
        )
    )
    db.add(
        FIStationTrustScore(
            tenant_id=1,
            station_id=station_id,
            network_id=network_id,
            computed_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            window_days=7,
            trust_score=60,
            level=StationTrustLevel.WATCHLIST,
            explain={"station_trust": {"trust_score": 60}},
        )
    )
    db.commit()


def test_risk_context_enriched(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    driver, vehicle, station, network, card = _seed_fleet_refs(db)
    _seed_scores(
        db,
        driver_id=str(driver.id),
        vehicle_id=str(vehicle.id),
        station_id=str(station.id),
        network_id=str(network.id),
    )
    result = build_risk_context_for_fuel_tx(
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle=vehicle,
        driver=driver,
        fuel_type=models.FuelType.DIESEL,
        amount_minor=1000,
        volume_ml=10000,
        occurred_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
        currency="RUB",
        subject_id="sub-1",
        policy_override_id=None,
        thresholds_override=None,
        policy_source="default",
        logistics_window_hours=None,
        severity_multiplier=None,
        db=db,
    )

    metadata = result.decision_context.metadata
    assert metadata["driver_score_level"] == DriverBehaviorLevel.HIGH.value
    assert metadata["station_trust_level"] == StationTrustLevel.WATCHLIST.value
    assert metadata["vehicle_efficiency_delta_pct"] == pytest.approx(0.0714)


def test_unified_explain_includes_fleet_intelligence(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        driver, vehicle, station, network, card = _seed_fleet_refs(db)
        _seed_scores(
            db,
            driver_id=str(driver.id),
            vehicle_id=str(vehicle.id),
            station_id=str(station.id),
            network_id=str(network.id),
        )
        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            station_id=station.id,
            network_id=network.id,
            occurred_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            fuel_type="DIESEL",
            volume_ml=15000,
            unit_price_minor=500,
            amount_total_minor=7500,
            currency="RUB",
            status=models.FuelTransactionStatus.SETTLED,
        )
        db.add(tx)
        db.commit()

    response = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}")
    assert response.status_code == 200
    payload = response.json()
    assert "fleet_intelligence" in payload["sections"]

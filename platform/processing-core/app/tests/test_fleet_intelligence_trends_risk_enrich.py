from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.crm import CRMClient, CRMClientStatus
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fleet_intelligence import (
    DriverBehaviorLevel,
    FIDriverScore,
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FITrendWindow,
)
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelNetworkStatus, FuelStation, FuelStationStatus, FuelType
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


def test_risk_context_trend_hint(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Driver",
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
    db.add_all([client, driver, vehicle, network, station])
    db.flush()
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
    )
    score = FIDriverScore(
        tenant_id=1,
        client_id="client-1",
        driver_id=str(driver.id),
        computed_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
        window_days=7,
        score=80,
        level=DriverBehaviorLevel.HIGH,
        explain={"driver_behavior": {"score": 80}},
    )
    trend = FITrendSnapshot(
        tenant_id=1,
        client_id="client-1",
        entity_type=FITrendEntityType.DRIVER,
        entity_id=str(driver.id),
        metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
        window=FITrendWindow.D7,
        current_value=80.0,
        baseline_value=70.0,
        delta=10.0,
        delta_pct=14.3,
        label=FITrendLabel.DEGRADING,
        computed_day=datetime(2025, 1, 5, tzinfo=timezone.utc).date(),
        computed_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
        explain={"top_factors": []},
    )
    db.add_all([card, score, trend])
    db.commit()

    result = build_risk_context_for_fuel_tx(
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle=vehicle,
        driver=driver,
        fuel_type=FuelType.DIESEL,
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
    assert metadata["fleet_trend_driver_label"] == FITrendLabel.DEGRADING.value
    assert "fleet_trend_degrading" in metadata["risk_hints"]

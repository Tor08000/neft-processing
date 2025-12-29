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
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FITrendWindow,
)
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
from app.services.explain.unified import build_unified_explain


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


def test_unified_explain_contains_trends(db_session: Tuple[Session, sessionmaker]):
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
        status=FuelTransactionStatus.SETTLED,
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
        computed_day=datetime(2025, 1, 11, tzinfo=timezone.utc).date(),
        computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        explain={"top_factors": []},
    )
    db.add_all([card, tx, trend])
    db.commit()

    response = build_unified_explain(db, fuel_tx_id=str(tx.id))
    sections = response.sections
    assert "fleet_trends" in sections
    trend_section = sections["fleet_trends"]["driver"]
    assert trend_section["label"] == FITrendLabel.DEGRADING.value
    assert "ухудшается" in trend_section["message"]

import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.db import Base
from app.models.fuel import FuelCard, FuelNetwork, FuelStation
from app.models.logistics import LogisticsRiskSignal, LogisticsRiskSignalType, LogisticsDeviationEvent, LogisticsDeviationEventType, LogisticsDeviationSeverity
from app.services.fuel.risk_context import build_risk_context_for_fuel_tx
from app.services.logistics.orders import create_order


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


def test_risk_signals_enriched_in_fuel_context(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    vehicle = models.FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="RISK123",
        status=models.FleetVehicleStatus.ACTIVE,
    )
    driver = models.FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Risk Driver",
        status=models.FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)

    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=models.LogisticsOrderType.DELIVERY,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
    )

    signal = LogisticsRiskSignal(
        tenant_id=1,
        client_id="client-1",
        order_id=str(order.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        signal_type=LogisticsRiskSignalType.FUEL_OFF_ROUTE,
        severity=90,
        ts=datetime.now(timezone.utc),
        explain={"note": "test"},
    )
    db.add(signal)
    deviation_event = LogisticsDeviationEvent(
        order_id=str(order.id),
        route_id=str(order.id),
        event_type=LogisticsDeviationEventType.OFF_ROUTE,
        ts=datetime.now(timezone.utc),
        lat=55.7,
        lon=37.6,
        distance_from_route_m=5000,
        stop_id=None,
        severity=LogisticsDeviationSeverity.HIGH,
        explain={"note": "off-route"},
    )
    db.add(deviation_event)

    network = FuelNetwork(name="RiskNet", provider_code="RNET", status=models.FuelNetworkStatus.ACTIVE)
    db.add(network)
    db.commit()
    db.refresh(network)

    station = FuelStation(
        network_id=str(network.id),
        station_network_id=None,
        station_code="RS-1",
        name="Risk Station",
        country="RU",
        region="MSK",
        city="Moscow",
        lat="55.75",
        lon="37.6",
        status=models.FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        tenant_id=1,
        client_id="client-1",
        card_token="risk-token",
        status=models.FuelCardStatus.ACTIVE,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
    )
    db.add_all([station, card])
    db.commit()
    db.refresh(station)
    db.refresh(card)

    result = build_risk_context_for_fuel_tx(
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle=vehicle,
        driver=driver,
        fuel_type=models.FuelType.DIESEL,
        amount_minor=1000,
        volume_ml=1000,
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        currency="RUB",
        subject_id="subject-1",
        policy_override_id=None,
        thresholds_override=None,
        policy_source="test",
        db=db,
    )
    summary = result.decision_context.metadata.get("logistics_signals")
    assert summary
    assert "FUEL_OFF_ROUTE" in summary
    assert summary["FUEL_OFF_ROUTE"]["count"] >= 1
    off_route_summary = result.decision_context.metadata.get("logistics_off_route_summary")
    assert off_route_summary
    assert off_route_summary["count"] >= 1

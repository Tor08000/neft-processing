from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation, FuelTransaction, OpsStationEvent
from app.services.fuel.station_automation import evaluate_station_health, evaluate_station_risk


def _sessionmaker() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    OpsStationEvent.__table__.create(bind=engine)
    return testing_session_local


def test_station_health_evaluator_sets_offline_and_writes_event() -> None:
    session_local = _sessionmaker()
    now = datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc)

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
            health_status="ONLINE",
            last_heartbeat=now - timedelta(minutes=31),
        )
        db.add(station)
        db.commit()

        result = evaluate_station_health(db, now=now)
        db.commit()

        refreshed = db.query(FuelStation).filter(FuelStation.id == station.id).one()
        event = db.query(OpsStationEvent).filter(OpsStationEvent.station_id == station.id).one()

    assert result["changed"] == 1
    assert refreshed.health_status == "OFFLINE"
    assert refreshed.health_source == "SYSTEM"
    assert event.event_type == "HEALTH_CHANGED"
    assert event.new_value == "OFFLINE"


def test_station_automation_respects_manual_locks_and_sets_red_risk() -> None:
    session_local = _sessionmaker()
    now = datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc)

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        locked_station = FuelStation(
            network_id=str(network.id),
            station_code="S-LOCK",
            name="locked",
            status=fuel_models.FuelStationStatus.ACTIVE,
            health_status="ONLINE",
            health_manual_lock=True,
            health_manual_until=now + timedelta(hours=1),
            risk_zone="GREEN",
            risk_manual_lock=True,
            risk_manual_until=now + timedelta(hours=1),
        )
        red_station = FuelStation(
            network_id=str(network.id),
            station_code="S-RED",
            name="red",
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="GREEN",
            health_status="ONLINE",
            last_heartbeat=now,
        )
        db.add_all([locked_station, red_station])
        db.commit()
        db.refresh(red_station)

        for i in range(5):
            db.add(
                FuelTransaction(
                    tenant_id=1,
                    client_id="c1",
                    card_id=str(red_station.id),
                    vehicle_id=None,
                    driver_id=None,
                    station_id=str(red_station.id),
                    network_id=str(network.id),
                    occurred_at=now - timedelta(hours=1) + timedelta(minutes=i),
                    fuel_type=fuel_models.FuelType.DIESEL,
                    volume_ml=1000,
                    unit_price_minor=100,
                    amount_total_minor=100,
                    currency="RUB",
                    status=fuel_models.FuelTransactionStatus.DECLINED,
                    meta={"risk_tags": ["STATION_RISK_RED"]},
                )
            )
        db.commit()

        health_result = evaluate_station_health(db, now=now)
        risk_result = evaluate_station_risk(db, now=now)
        db.commit()

        locked = db.query(FuelStation).filter(FuelStation.id == locked_station.id).one()
        red = db.query(FuelStation).filter(FuelStation.id == red_station.id).one()
        risk_event = (
            db.query(OpsStationEvent)
            .filter(OpsStationEvent.station_id == red_station.id)
            .filter(OpsStationEvent.event_type == "RISK_CHANGED")
            .one()
        )

    assert health_result["skipped_manual"] == 1
    assert risk_result["skipped_manual"] == 1
    assert locked.risk_zone == "GREEN"
    assert red.risk_zone == "RED"
    assert risk_event.new_value == "RED"

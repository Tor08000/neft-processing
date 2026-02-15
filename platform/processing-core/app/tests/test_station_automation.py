from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation, FuelTransaction, OpsStationEvent
from app.services.fuel.station_automation import (
    evaluate_station_health,
    evaluate_station_risk_downgrade_daily,
    evaluate_station_risk_escalation,
)


def _sessionmaker() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    OpsStationEvent.__table__.create(bind=engine)
    return testing_session_local


def _add_risk_tx(db: Session, *, station_id: str, network_id: str, when: datetime, tags: list[str]) -> None:
    db.add(
        FuelTransaction(
            tenant_id=1,
            client_id="c1",
            card_id=str(station_id),
            vehicle_id=None,
            driver_id=None,
            station_id=str(station_id),
            network_id=str(network_id),
            occurred_at=when,
            fuel_type=fuel_models.FuelType.DIESEL,
            volume_ml=1000,
            unit_price_minor=100,
            amount_total_minor=100,
            currency="RUB",
            status=fuel_models.FuelTransactionStatus.DECLINED,
            meta={"risk_tags": tags},
        )
    )


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


def test_station_risk_escalation_applies_thresholds() -> None:
    session_local = _sessionmaker()
    now = datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc)

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        yellow_station = FuelStation(
            network_id=str(network.id),
            station_code="S-Y",
            name="yellow",
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="GREEN",
        )
        red_station = FuelStation(
            network_id=str(network.id),
            station_code="S-R",
            name="red",
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="GREEN",
        )
        db.add_all([yellow_station, red_station])
        db.commit()

        for i in range(2):
            _add_risk_tx(
                db,
                station_id=str(yellow_station.id),
                network_id=str(network.id),
                when=now - timedelta(hours=1) + timedelta(minutes=i),
                tags=["STATION_RISK_YELLOW"],
            )

        for i in range(5):
            _add_risk_tx(
                db,
                station_id=str(red_station.id),
                network_id=str(network.id),
                when=now - timedelta(hours=2) + timedelta(minutes=i),
                tags=["STATION_RISK_RED"],
            )

        db.commit()

        result = evaluate_station_risk_escalation(db, now=now)
        db.commit()

        updated_yellow = db.query(FuelStation).filter(FuelStation.id == yellow_station.id).one()
        updated_red = db.query(FuelStation).filter(FuelStation.id == red_station.id).one()

    assert result["changed"] == 2
    assert updated_yellow.risk_zone == "YELLOW"
    assert updated_red.risk_zone == "RED"


def test_station_risk_downgrade_daily_updates_streak_and_downgrades() -> None:
    session_local = _sessionmaker()
    now = datetime(2026, 2, 15, 3, 10, tzinfo=timezone.utc)

    with session_local() as db:
        network = FuelNetwork(name="NET", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(network)
        db.commit()
        db.refresh(network)

        red_station = FuelStation(
            network_id=str(network.id),
            station_code="S-RED",
            name="red",
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="RED",
            risk_red_clear_streak_days=2,
            risk_yellow_clear_streak_days=0,
        )
        yellow_station = FuelStation(
            network_id=str(network.id),
            station_code="S-Y",
            name="yellow",
            status=fuel_models.FuelStationStatus.ACTIVE,
            risk_zone="YELLOW",
            risk_red_clear_streak_days=6,
            risk_yellow_clear_streak_days=6,
        )
        db.add_all([red_station, yellow_station])
        db.commit()

        result = evaluate_station_risk_downgrade_daily(db, now=now)
        db.commit()

        downgraded_red = db.query(FuelStation).filter(FuelStation.id == red_station.id).one()
        downgraded_yellow = db.query(FuelStation).filter(FuelStation.id == yellow_station.id).one()

    assert result["streak_updated"] == 2
    assert result["changed"] == 2
    assert downgraded_red.risk_zone == "YELLOW"
    assert downgraded_red.risk_red_clear_streak_days == 3
    assert downgraded_yellow.risk_zone == "GREEN"
    assert downgraded_yellow.risk_yellow_clear_streak_days == 7


def test_station_automation_respects_manual_risk_lock() -> None:
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
            risk_zone="GREEN",
            risk_manual_lock=True,
            risk_manual_until=now + timedelta(hours=1),
        )
        db.add(locked_station)
        db.commit()

        for i in range(10):
            _add_risk_tx(
                db,
                station_id=str(locked_station.id),
                network_id=str(network.id),
                when=now - timedelta(hours=1) + timedelta(minutes=i),
                tags=["STATION_RISK_RED"],
            )
        db.commit()

        escalation = evaluate_station_risk_escalation(db, now=now)
        daily = evaluate_station_risk_downgrade_daily(db, now=now)
        db.commit()

        locked = db.query(FuelStation).filter(FuelStation.id == locked_station.id).one()

    assert escalation["skipped_manual"] == 1
    assert daily["skipped_manual"] == 1
    assert locked.risk_zone == "GREEN"

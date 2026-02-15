from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import fuel as fuel_models
from app.models.fuel import FuelNetwork, FuelStation, FuelStationPrice


def _db() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    FuelNetwork.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelStationPrice.__table__.create(bind=engine)
    return session_local


def _seed_station(session_local: sessionmaker) -> str:
    with session_local() as db:
        net = FuelNetwork(name="NET", provider_code="NET-C", status=fuel_models.FuelNetworkStatus.ACTIVE)
        db.add(net)
        db.commit()
        db.refresh(net)
        station = FuelStation(network_id=str(net.id), station_code="SC", name="SC", status=fuel_models.FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)
        return str(station.id)


def test_price_must_be_positive() -> None:
    session_local = _db()
    station_id = _seed_station(session_local)
    with session_local() as db, pytest.raises(IntegrityError):
        db.add(
            FuelStationPrice(
                station_id=station_id,
                product_code="AI95",
                price=0,
                currency="RUB",
                status=fuel_models.FuelStationPriceStatus.ACTIVE,
                source=fuel_models.FuelStationPriceSource.MANUAL,
            )
        )
        db.commit()


def test_valid_window_constraint() -> None:
    session_local = _db()
    station_id = _seed_station(session_local)
    now = datetime.now(timezone.utc)
    with session_local() as db, pytest.raises(IntegrityError):
        db.add(
            FuelStationPrice(
                station_id=station_id,
                product_code="AI95",
                price=10,
                currency="RUB",
                status=fuel_models.FuelStationPriceStatus.ACTIVE,
                source=fuel_models.FuelStationPriceSource.MANUAL,
                valid_from=now,
                valid_to=now - timedelta(days=1),
            )
        )
        db.commit()

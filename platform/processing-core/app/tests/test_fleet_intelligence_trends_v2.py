from datetime import date, datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.crm import CRMClient, CRMClientStatus
from app.models.fleet_intelligence import (
    DriverBehaviorLevel,
    FIDriverScore,
    FIStationTrustScore,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FIVehicleEfficiencyScore,
    StationTrustLevel,
)
from app.services.fleet_intelligence import trends


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


def _seed_client(db: Session) -> CRMClient:
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    db.add(client)
    db.commit()
    return client


def test_trend_labels_v2(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    _seed_client(db)
    day = date(2025, 1, 31)
    driver_id = str(uuid4())
    stable_driver_id = str(uuid4())
    station_id = str(uuid4())
    vehicle_id = str(uuid4())

    db.add_all(
        [
            FIDriverScore(
                tenant_id=1,
                client_id="client-1",
                driver_id=driver_id,
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=7,
                score=80,
                level=DriverBehaviorLevel.HIGH,
                explain={"driver_behavior": {"top_factors": [{"factor": "off_route", "value": 10}]}},
            ),
            FIDriverScore(
                tenant_id=1,
                client_id="client-1",
                driver_id=driver_id,
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=30,
                score=70,
                level=DriverBehaviorLevel.MEDIUM,
                explain={"driver_behavior": {"top_factors": [{"factor": "night_fuel", "value": 4}]}},
            ),
            FIDriverScore(
                tenant_id=1,
                client_id="client-1",
                driver_id=stable_driver_id,
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=7,
                score=52,
                level=DriverBehaviorLevel.MEDIUM,
                explain={"driver_behavior": {"top_factors": []}},
            ),
            FIDriverScore(
                tenant_id=1,
                client_id="client-1",
                driver_id=stable_driver_id,
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=30,
                score=50,
                level=DriverBehaviorLevel.MEDIUM,
                explain={"driver_behavior": {"top_factors": []}},
            ),
            FIStationTrustScore(
                tenant_id=1,
                station_id=station_id,
                network_id=str(uuid4()),
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=30,
                trust_score=60,
                level=StationTrustLevel.WATCHLIST,
                explain={"station_trust": {"reasons": ["decline_rate", "risk_block_rate"]}},
            ),
            FIStationTrustScore(
                tenant_id=1,
                station_id=station_id,
                network_id=str(uuid4()),
                computed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                window_days=30,
                trust_score=72,
                level=StationTrustLevel.TRUSTED,
                explain={"station_trust": {"reasons": ["decline_rate"]}},
            ),
            FIVehicleEfficiencyScore(
                tenant_id=1,
                client_id="client-1",
                vehicle_id=vehicle_id,
                computed_at=datetime(2025, 1, 31, tzinfo=timezone.utc),
                window_days=7,
                efficiency_score=80,
                baseline_ml_per_100km=280.0,
                actual_ml_per_100km=300.0,
                delta_pct=0.10,
                explain={"vehicle_efficiency": {"efficiency_score": 80}},
            ),
            FIVehicleEfficiencyScore(
                tenant_id=1,
                client_id="client-1",
                vehicle_id=vehicle_id,
                computed_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
                window_days=7,
                efficiency_score=70,
                baseline_ml_per_100km=280.0,
                actual_ml_per_100km=290.0,
                delta_pct=0.03,
                explain={"vehicle_efficiency": {"efficiency_score": 70}},
            ),
        ]
    )
    db.commit()

    trends.compute_trends_for_client(db, client_id="client-1", day=day)
    db.commit()

    driver_trend = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_id == driver_id)
        .filter(FITrendSnapshot.metric == FITrendMetric.DRIVER_BEHAVIOR_SCORE)
        .first()
    )
    assert driver_trend is not None
    assert driver_trend.label == FITrendLabel.DEGRADING

    stable_driver_trend = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_id == stable_driver_id)
        .filter(FITrendSnapshot.metric == FITrendMetric.DRIVER_BEHAVIOR_SCORE)
        .first()
    )
    assert stable_driver_trend is not None
    assert stable_driver_trend.label == FITrendLabel.STABLE

    station_trend = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_id == station_id)
        .filter(FITrendSnapshot.metric == FITrendMetric.STATION_TRUST_SCORE)
        .first()
    )
    assert station_trend is not None
    assert station_trend.label == FITrendLabel.DEGRADING

    vehicle_trend = (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_id == vehicle_id)
        .filter(FITrendSnapshot.metric == FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT)
        .first()
    )
    assert vehicle_trend is not None
    assert vehicle_trend.label == FITrendLabel.DEGRADING

from datetime import date, datetime, timezone, timedelta
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
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FITrendWindow,
)
from app.models.fleet_intelligence_actions import FIInsightSeverity, FIInsightType
from app.services.fleet_intelligence.control import insights


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


def test_generate_insights_from_trends(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    _seed_client(db)
    day = date(2025, 1, 11)
    driver_id = str(uuid4())
    for offset in range(2):
        computed_day = day - timedelta(days=offset)
        db.add(
            FITrendSnapshot(
                tenant_id=1,
                client_id="client-1",
                entity_type=FITrendEntityType.DRIVER,
                entity_id=driver_id,
                metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
                window=FITrendWindow.D7,
                current_value=75.0,
                baseline_value=60.0,
                delta=15.0,
                delta_pct=25.0,
                label=FITrendLabel.DEGRADING,
                computed_day=computed_day,
                computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            )
        )
    db.add(
        FIDriverScore(
            tenant_id=1,
            client_id="client-1",
            driver_id=driver_id,
            computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            window_days=7,
            score=60,
            level=DriverBehaviorLevel.MEDIUM,
        )
    )
    db.commit()

    results = insights.generate_insights_for_day(db, day=day)
    db.commit()

    assert results
    insight = results[0]
    assert insight.insight_type == FIInsightType.DRIVER_BEHAVIOR_DEGRADING
    assert insight.severity == FIInsightSeverity.MEDIUM


def test_critical_severity_from_score(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    _seed_client(db)
    day = date(2025, 1, 11)
    driver_id = str(uuid4())
    for offset in range(2):
        computed_day = day - timedelta(days=offset)
        db.add(
            FITrendSnapshot(
                tenant_id=1,
                client_id="client-1",
                entity_type=FITrendEntityType.DRIVER,
                entity_id=driver_id,
                metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
                window=FITrendWindow.D7,
                current_value=95.0,
                baseline_value=70.0,
                delta=25.0,
                delta_pct=35.0,
                label=FITrendLabel.DEGRADING,
                computed_day=computed_day,
                computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            )
        )
    db.add(
        FIDriverScore(
            tenant_id=1,
            client_id="client-1",
            driver_id=driver_id,
            computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            window_days=7,
            score=95,
            level=DriverBehaviorLevel.VERY_HIGH,
        )
    )
    db.commit()

    results = insights.generate_insights_for_day(db, day=day)
    db.commit()

    assert results
    assert results[0].severity == FIInsightSeverity.CRITICAL

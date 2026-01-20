from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType, DecisionOutcome
from app.services.decision_memory import cooldown as memory_cooldown


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_cooldown_after_failed_streak(db_session: Session) -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    for offset in (1, 3):
        outcome = DecisionOutcome(
            tenant_id=1,
            client_id="client-1",
            entity_type=DecisionMemoryEntityType.DRIVER,
            entity_id="driver-1",
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            applied_at=now - timedelta(days=offset),
            measured_at=now - timedelta(days=offset),
            window_days=7,
            effect_label=DecisionMemoryEffectLabel.NO_CHANGE,
        )
        db_session.add(outcome)
    db_session.commit()

    status = memory_cooldown.evaluate_cooldown(
        db_session,
        entity_type=DecisionMemoryEntityType.DRIVER,
        entity_id="driver-1",
        action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
        now=now,
    )

    assert status.cooldown is True
    assert "no improvement" in (status.reason or "").lower()

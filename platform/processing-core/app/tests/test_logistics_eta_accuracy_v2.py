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
from app.services.logistics import eta, repository
from app.services.logistics.defaults import ETA_ACCURACY_DEFAULTS
from app.services.logistics.orders import complete_order, create_order, start_order


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


def test_eta_accuracy_on_completion(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    planned_start = datetime.now(timezone.utc) - timedelta(hours=1)
    planned_end = datetime.now(timezone.utc) + timedelta(hours=1)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=models.LogisticsOrderType.TRIP,
        planned_start_at=planned_start,
        planned_end_at=planned_end,
    )

    start_order(db, order_id=str(order.id))
    eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")

    complete_order(
        db,
        order_id=str(order.id),
        completed_at=planned_end + timedelta(minutes=ETA_ACCURACY_DEFAULTS.eta_error_high_minutes + 70),
    )
    accuracy = repository.list_eta_accuracy(db, order_id=str(order.id))
    assert accuracy
    completion = next((item for item in accuracy if item.error_minutes is not None), None)
    assert completion is not None
    assert completion.error_minutes >= ETA_ACCURACY_DEFAULTS.eta_error_high_minutes
    signals = repository.list_risk_signals(db, order_id=str(order.id))
    assert any(signal.signal_type.value == "ETA_ANOMALY" for signal in signals)

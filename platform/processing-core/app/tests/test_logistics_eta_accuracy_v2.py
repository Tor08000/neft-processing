import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Tuple

import pytest
from sqlalchemy.orm import Session, sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models import logistics as logistics_models
from app.models.logistics import LogisticsETAAccuracy, LogisticsRiskSignal
from app.services.logistics import eta, eta_accuracy
from app.services.logistics.defaults import ETA_ACCURACY_DEFAULTS
from app.services.logistics.orders import complete_order, create_order, start_order
from app.tests._logistics_route_harness import logistics_session_context


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    with logistics_session_context() as ctx:
        yield ctx


def _list_eta_accuracy(db: Session, *, order_id: str) -> list[LogisticsETAAccuracy]:
    return (
        db.query(LogisticsETAAccuracy)
        .filter(LogisticsETAAccuracy.order_id == order_id)
        .order_by(LogisticsETAAccuracy.computed_at.desc())
        .all()
    )


def _list_risk_signals(db: Session, *, order_id: str) -> list[LogisticsRiskSignal]:
    return (
        db.query(LogisticsRiskSignal)
        .filter(LogisticsRiskSignal.order_id == order_id)
        .order_by(LogisticsRiskSignal.ts.desc(), LogisticsRiskSignal.created_at.desc())
        .all()
    )


def test_eta_accuracy_on_completion(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Tuple[Session, sessionmaker],
):
    monkeypatch.setenv("LOGISTICS_SERVICE_ENABLED", "0")
    monkeypatch.setattr(
        "app.services.logistics.eta.get_settings",
        lambda: SimpleNamespace(LOGISTICS_SERVICE_ENABLED=False),
    )
    db, _ = db_session
    planned_start = datetime.now(timezone.utc) - timedelta(hours=1)
    planned_end = datetime.now(timezone.utc) + timedelta(hours=1)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.TRIP,
        planned_start_at=planned_start,
        planned_end_at=planned_end,
    )

    start_order(db, order_id=str(order.id))
    eta.compute_eta_snapshot(db, order_id=str(order.id), reason="test")

    order = complete_order(
        db,
        order_id=str(order.id),
        completed_at=planned_end + timedelta(minutes=ETA_ACCURACY_DEFAULTS.eta_error_high_minutes + 70),
    )
    recorded = eta_accuracy.record_completion(db, order=order)
    assert recorded is not None
    accuracy = _list_eta_accuracy(db, order_id=str(order.id))
    assert accuracy
    completion = next((item for item in accuracy if item.error_minutes is not None), None)
    assert completion is not None
    assert completion.error_minutes >= ETA_ACCURACY_DEFAULTS.eta_error_high_minutes
    signals = _list_risk_signals(db, order_id=str(order.id))
    assert any(signal.signal_type.value == "ETA_ANOMALY" for signal in signals)

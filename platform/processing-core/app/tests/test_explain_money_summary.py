from datetime import date
from uuid import uuid4

import pytest

from app.models.invoice import Invoice
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyInvariantSnapshot, MoneyInvariantSnapshotPhase
from app.services.explain.unified import build_unified_explain
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType
from app.tests._explain_test_harness import EXPLAIN_UNIFIED_FUEL_TEST_TABLES
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture
def session():
    with scoped_session_context(tables=EXPLAIN_UNIFIED_FUEL_TEST_TABLES) as db:
        yield db


def test_money_summary_and_invariants(session):
    invoice = Invoice(
        id=str(uuid4()),
        client_id="client-1",
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        currency="RUB",
        total_with_tax=120000,
        amount_paid=80000,
        amount_due=40000,
        amount_refunded=0,
    )
    session.add(invoice)
    session.flush()

    event = MoneyFlowEvent(
        tenant_id=1,
        client_id="client-1",
        flow_type=MoneyFlowType.INVOICE_PAYMENT,
        flow_ref_id=invoice.id,
        state_from=MoneyFlowState.DRAFT,
        state_to=MoneyFlowState.AUTHORIZED,
        event_type=MoneyFlowEventType.AUTHORIZE,
        idempotency_key="evt-1",
    )
    session.add(event)
    session.flush()

    snapshot = MoneyInvariantSnapshot(
        tenant_id=1,
        client_id="client-1",
        flow_type=MoneyFlowType.INVOICE_PAYMENT,
        flow_ref_id=invoice.id,
        event_id=event.id,
        phase=MoneyInvariantSnapshotPhase.BEFORE,
        snapshot_hash="hash",
        snapshot_json={"invoice": {"amount_due": 40000}},
        passed=False,
        violations=["invoice.amount_due"],
    )
    session.add(snapshot)
    session.commit()

    payload = build_unified_explain(session, invoice_id=invoice.id)
    money_summary = payload.sections["money"]["money_summary"]

    assert money_summary == {
        "charged": 120000,
        "paid": 80000,
        "due": 40000,
        "refunded": 0,
        "invariants": "FAILED",
        "replay_link": None,
    }

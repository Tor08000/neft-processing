from datetime import datetime, timezone

import pytest

from app.db import Base, engine, get_sessionmaker
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFormat
from app.models.risk_types import RiskDecisionType
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
from app.services.decision.scoring import StubRiskScorer
from app.services.payout_exports import PayoutExportError, create_payout_export


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _fixed_now() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _seed_global_thresholds():
    session = get_sessionmaker()()
    session.add_all(
        [
            RiskThresholdSet(
                id="global-payment",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
            ),
            RiskThresholdSet(
                id="global-payout",
                subject_type=RiskSubjectType.PAYOUT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYOUT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
            ),
            RiskThresholdSet(
                id="global-document",
                subject_type=RiskSubjectType.DOCUMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.DOCUMENT_FINALIZE,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
            ),
        ]
    )
    session.commit()
    session.close()


def test_decision_engine_determinism():
    session = get_sessionmaker()()
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=20), now_provider=_fixed_now)
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"single_transaction_limit": 1000},
    )

    first = engine_instance.evaluate(context)
    second = engine_instance.evaluate(context)

    assert first.outcome == second.outcome
    assert first.risk_score == second.risk_score
    assert first.rule_hits == second.rule_hits
    assert first.explain == second.explain
    assert first.decision_version == second.decision_version
    session.close()


def test_rules_limit_decline():
    session = get_sessionmaker()()
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10), now_provider=_fixed_now)
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=2_000,
        currency="RUB",
        history={},
        metadata={"single_transaction_limit": 1000},
    )

    result = engine_instance.evaluate(context)
    assert result.outcome == "DECLINE"
    session.close()


def test_rules_blocked_client_declines_action():
    session = get_sessionmaker()()
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10), now_provider=_fixed_now)
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"client_status": "BLOCKED"},
    )

    result = engine_instance.evaluate(context)
    assert result.outcome == "DECLINE"
    assert result.risk_decision == RiskDecisionType.BLOCK
    session.close()


def test_rules_normal_payment_allow():
    session = get_sessionmaker()()
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10), now_provider=_fixed_now)
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"single_transaction_limit": 1000},
    )

    result = engine_instance.evaluate(context)
    assert result.outcome == "ALLOW"
    session.close()


def test_payout_export_open_period_declines_via_decision_engine():
    session = get_sessionmaker()()
    period = BillingPeriod(
        id="period-1",
        period_type=BillingPeriodType.ADHOC,
        start_at=_fixed_now(),
        end_at=_fixed_now(),
        tz="UTC",
        status=BillingPeriodStatus.OPEN,
    )
    batch = PayoutBatch(
        id="batch-1",
        tenant_id=1,
        partner_id="partner-1",
        date_from=period.start_at.date(),
        date_to=period.end_at.date(),
        state=PayoutBatchState.READY,
        meta={"billing_period_id": period.id},
    )
    session.add_all([period, batch])
    session.commit()

    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "tester"}
    with pytest.raises(PayoutExportError) as exc:
        create_payout_export(
            session,
            batch_id=batch.id,
            export_format=PayoutExportFormat.CSV,
            provider=None,
            external_ref=None,
            bank_format_code=None,
            token=token,
        )
    assert "decision_decline" in str(exc.value)
    session.close()


def test_document_finalize_without_ack_declines():
    session = get_sessionmaker()()
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10), now_provider=_fixed_now)
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="CLIENT",
        action=DecisionAction.DOCUMENT_FINALIZE,
        history={},
        metadata={
            "document_type": "INVOICE",
            "document_acknowledged": False,
        },
    )

    result = engine_instance.evaluate(context)
    assert result.outcome == "DECLINE"
    session.close()

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import OperationStatus
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFormat
from app.models.terminal import Terminal
from app.models.risk_score import RiskLevel
from app.services.accounting_export_service import AccountingExportRiskDeclined, AccountingExportService
from app.services.decision import DecisionEngine, DecisionOutcome, DecisionResult
from app.services.payout_exports import PayoutExportError, create_payout_export
from app.services import transactions_service


class _ApprovedLimits:
    approved = True
    daily_limit = None
    limit_per_tx = None
    used_today = None
    new_used_today = None
    applied_rule_id = "rule-1"

    def model_dump(self):
        return {"approved": True, "applied_rule_id": self.applied_rule_id}


def _decline_result() -> DecisionResult:
    return DecisionResult(
        decision_id=str(uuid4()),
        decision_version="1",
        outcome=DecisionOutcome.DECLINE,
        risk_score=80,
        risk_level=RiskLevel.HIGH,
        explain={"reason_codes": ["test_decline"], "rules_fired": ["TEST_RULE"]},
    )


def test_authorize_operation_declines_on_decision_engine(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(transactions_service, "evaluate_limits_locally", lambda *_, **__: _ApprovedLimits())
    monkeypatch.setattr(transactions_service, "_evaluate_risk", lambda *_args, **_kwargs: pytest.fail("risk engine"))
    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _decline_result())

    client_id = uuid4()
    with SessionLocal() as session:
        session.add(Client(id=client_id, name="Client", status="ACTIVE"))
        session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE"))
        session.add(Merchant(id="merchant-1", name="M", status="ACTIVE"))
        session.add(Terminal(id="terminal-1", merchant_id="merchant-1", status="ACTIVE"))
        session.commit()

        op = transactions_service.authorize_operation(
            session,
            client_id=str(client_id),
            card_id="card-1",
            terminal_id="terminal-1",
            merchant_id="merchant-1",
            tariff_id=None,
            product_id=None,
            product_type=None,
            amount=5000,
            currency="RUB",
            ext_operation_id="ext-decision-1",
            quantity=None,
            unit_price=None,
            mcc=None,
            product_category=None,
            tx_type=None,
            client_group_id=None,
            card_group_id=None,
        )

        assert op.status == OperationStatus.DECLINED
        assert op.response_code == "RISK_SCORE_DECLINE"
        assert op.risk_payload["decision_engine"]["outcome"] == "DECLINE"


def test_payout_export_declines_on_decision_engine(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _decline_result())

    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1"}
    with SessionLocal() as session:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.FINALIZED,
        )
        session.add(period)
        session.flush()
        batch = PayoutBatch(
            tenant_id=1,
            partner_id="partner-1",
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 2),
            state=PayoutBatchState.READY,
            total_amount=Decimal("100.00"),
            total_qty=Decimal("0.000"),
            operations_count=0,
            meta={"billing_period_id": period.id},
        )
        session.add(batch)
        session.commit()

        with pytest.raises(PayoutExportError, match="risk_decline"):
            create_payout_export(
                session,
                batch_id=batch.id,
                export_format=PayoutExportFormat.CSV,
                provider=None,
                external_ref=None,
                token=token,
            )


def test_accounting_export_declines_on_decision_engine(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _decline_result())

    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.FINALIZED,
    )

    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1"}
    with SessionLocal() as session:
        session.add(period)
        session.commit()

        service = AccountingExportService(session)
        with pytest.raises(AccountingExportRiskDeclined, match="risk_decline"):
            service.create_export(
                period_id=period.id,
                export_type=AccountingExportType.CHARGES,
                export_format=AccountingExportFormat.CSV,
                request_ctx=None,
                token=token,
            )

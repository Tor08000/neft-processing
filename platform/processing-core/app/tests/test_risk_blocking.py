from datetime import datetime, timezone

import pytest

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.card import Card
from app.models.client import Client
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.merchant import Merchant
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFile, PayoutExportFormat
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.models.terminal import Terminal
from app.services.accounting_export_service import AccountingExportRiskDeclined, AccountingExportService
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.payout_exports import PayoutExportError, create_payout_export
from app.services.transactions_service import authorize_operation
from app.main import app
from app.models.audit_log import AuditLog


def _seed_payment_refs(session):
    client = Client(id="client-1", name="Client", status="ACTIVE")
    session.add(client)
    session.add(Card(id="card-1", client_id="client-1", status="ACTIVE"))
    session.add(Merchant(id="merchant-1", name="M", status="ACTIVE"))
    session.add(Terminal(id="terminal-1", merchant_id="merchant-1", status="ACTIVE"))
    session.commit()
    return client.id


def _seed_thresholds(
    session,
    *,
    threshold_set_id: str,
    subject_type: RiskSubjectType,
    action: RiskThresholdAction,
    block_threshold: int = 5,
):
    session.add(
        RiskThresholdSet(
            id=threshold_set_id,
            subject_type=subject_type,
            scope=RiskThresholdScope.GLOBAL,
            action=action,
            block_threshold=block_threshold,
            review_threshold=3,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    )
    session.add(
        RiskPolicy(
            id=f"policy-{threshold_set_id}",
            subject_type=subject_type,
            tenant_id=None,
            client_id=None,
            provider=None,
            currency=None,
            country=None,
            threshold_set_id=threshold_set_id,
            model_selector="risk_v4",
            priority=10,
            active=True,
        )
    )
    session.commit()


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_accounting_export_blocked_by_thresholds():
    session = SessionLocal()
    try:
        threshold_set = RiskThresholdSet(
            id="exports_v4",
            subject_type=RiskSubjectType.EXPORT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.EXPORT,
            block_threshold=10,
            review_threshold=5,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        policy = RiskPolicy(
            id="EXPORT_POLICY",
            subject_type=RiskSubjectType.EXPORT,
            tenant_id=None,
            client_id=None,
            provider=None,
            currency=None,
            country=None,
            threshold_set_id="exports_v4",
            model_selector="risk_v4",
            priority=10,
            active=True,
        )
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.FINALIZED,
        )
        session.add_all([threshold_set, policy, period])
        session.commit()

        service = AccountingExportService(session)
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1"}
        with pytest.raises(AccountingExportRiskDeclined, match="risk_decline"):
            service.create_export(
                period_id=period.id,
                export_type=AccountingExportType.CHARGES,
                export_format=AccountingExportFormat.CSV,
                request_ctx=None,
                token=token,
            )
    finally:
        session.close()


def test_payment_block_prevents_posting_and_audits():
    session = SessionLocal()
    try:
        _seed_thresholds(
            session,
            threshold_set_id="payment-block",
            subject_type=RiskSubjectType.PAYMENT,
            action=RiskThresholdAction.PAYMENT,
        )
        client_id = _seed_payment_refs(session)

        op = authorize_operation(
            session,
            client_id=client_id,
            card_id="card-1",
            terminal_id="terminal-1",
            merchant_id="merchant-1",
            tariff_id=None,
            product_id=None,
            product_type=None,
            amount=5000,
            currency="RUB",
            ext_operation_id="risk-block-payment",
        )

        assert op.status.value == "DECLINED"
        assert op.response_code == "RISK_SCORE_DECLINE"
        assert op.risk_payload["decision_engine"]["explain"]["decision_hash"]
        assert op.risk_payload["decision_engine"]["explain"]["decision"] == "BLOCK"
        assert (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "RISK_DECISION_BLOCKED")
            .filter(AuditLog.entity_type == "risk_decision")
            .count()
            == 1
        )
    finally:
        session.close()


def test_payout_block_prevents_export_and_audits():
    session = SessionLocal()
    try:
        _seed_thresholds(
            session,
            threshold_set_id="payout-block",
            subject_type=RiskSubjectType.PAYOUT,
            action=RiskThresholdAction.PAYOUT,
        )
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
            date_from=period.start_at.date(),
            date_to=period.end_at.date(),
            state=PayoutBatchState.READY,
            total_amount=100,
            total_qty=0,
            operations_count=0,
            meta={"billing_period_id": period.id},
        )
        session.add(batch)
        session.commit()

        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1"}
        with pytest.raises(PayoutExportError, match="risk_decline"):
            create_payout_export(
                session,
                batch_id=batch.id,
                export_format=PayoutExportFormat.CSV,
                provider=None,
                external_ref=None,
                token=token,
            )

        assert session.query(PayoutExportFile).count() == 0
        assert (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "RISK_DECISION_BLOCKED")
            .filter(AuditLog.entity_type == "risk_decision")
            .count()
            == 1
        )
        decision_record = session.query(DecisionResultRecord).one()
        assert decision_record.explain["decision_hash"]
        assert decision_record.outcome == DecisionOutcome.DECLINE.value
    finally:
        session.close()


def test_document_finalize_blocked_with_explain_and_audit(make_jwt):
    session = SessionLocal()
    try:
        _seed_thresholds(
            session,
            threshold_set_id="document-block",
            subject_type=RiskSubjectType.DOCUMENT,
            action=RiskThresholdAction.DOCUMENT_FINALIZE,
        )
        document = Document(
            tenant_id=1,
            client_id="client-1",
            document_type=DocumentType.INVOICE,
            period_from=datetime(2025, 1, 1).date(),
            period_to=datetime(2025, 1, 31).date(),
            status=DocumentStatus.ACKNOWLEDGED,
            version=1,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentFile(
                document_id=document.id,
                file_type=DocumentFileType.PDF,
                bucket="docs",
                object_key=f"docs/{document.id}.pdf",
                sha256="hash-1",
                size_bytes=100,
                content_type="application/pdf",
            )
        )
        session.commit()

        admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"))
        with TestClient(app, headers={"Authorization": f"Bearer {admin_token}"}) as api_client:
            response = api_client.post(f"/api/v1/admin/documents/{document.id}/finalize")
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert detail["reason"] == "risk_decline"
            assert detail["explain"]["decision_hash"]

        session.refresh(document)
        assert document.status == DocumentStatus.ACKNOWLEDGED
        assert (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "RISK_DECISION_BLOCKED")
            .filter(AuditLog.entity_type == "risk_decision")
            .count()
            == 1
        )
    finally:
        session.close()


def test_block_audit_links_to_explain():
    session = SessionLocal()
    try:
        _seed_thresholds(
            session,
            threshold_set_id="payment-audit",
            subject_type=RiskSubjectType.PAYMENT,
            action=RiskThresholdAction.PAYMENT,
        )
        engine_instance = DecisionEngine(session)
        ctx = DecisionContext(
            tenant_id=1,
            client_id="client-1",
            actor_type="SYSTEM",
            action=DecisionAction.PAYMENT_AUTHORIZE,
            amount=500,
            currency="RUB",
            history={},
            metadata={"subject_id": "op-audit"},
        )

        result = engine_instance.evaluate(ctx)

        audit_entry = (
            session.query(AuditLog)
            .filter(AuditLog.event_type == "RISK_DECISION_BLOCKED")
            .filter(AuditLog.entity_type == "risk_decision")
            .one()
        )
        decision_record = (
            session.query(DecisionResultRecord)
            .filter(DecisionResultRecord.decision_id == audit_entry.after["decision_id"])
            .one()
        )
        assert result.explain["decision_hash"] == decision_record.explain["decision_hash"]
    finally:
        session.close()

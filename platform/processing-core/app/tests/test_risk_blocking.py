from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from sqlalchemy import Column, String, Table

from app.api.dependencies.admin import require_admin_user
from app.db import Base
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.card import Card
from app.models.client import Client
from app.models.client_actions import DocumentAcknowledgement
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.merchant import Merchant
from app.models.operation import Operation
from app.models.payout_batch import PayoutBatch, PayoutBatchState, PayoutItem
from app.models.payout_export_file import PayoutExportFile, PayoutExportFormat
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.models.terminal import Terminal
from app.routers.admin import documents as admin_documents_router
from app.services.accounting_export_service import AccountingExportRiskDeclined, AccountingExportService
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.payout_exports import PayoutExportError, create_payout_export
from app.services.transactions_service import authorize_operation
from app.models.audit_log import AuditLog
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


if "fuel_stations" not in Base.metadata.tables:
    Table(
        "fuel_stations",
        Base.metadata,
        Column("id", String(36), primary_key=True),
        extend_existing=True,
    )


CLIENT_ID = "11111111-1111-1111-1111-111111111111"
ADMIN_TOKEN = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1", "user_id": "admin-1"}

RISK_BLOCKING_TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    Client.__table__,
    Card.__table__,
    Merchant.__table__,
    Terminal.__table__,
    Base.metadata.tables["fuel_stations"],
    Operation.__table__,
    DecisionResultRecord.__table__,
    Document.__table__,
    DocumentFile.__table__,
    DocumentAcknowledgement.__table__,
    PayoutBatch.__table__,
    PayoutItem.__table__,
    PayoutExportFile.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThreshold.__table__,
    RiskThresholdSet.__table__,
    RiskTrainingSnapshot.__table__,
)


def _seed_payment_refs(session):
    client = Client(id=UUID(CLIENT_ID), name="Client", status="ACTIVE")
    session.add(client)
    session.add(Card(id="card-1", client_id=CLIENT_ID, status="ACTIVE"))
    session.add(Merchant(id="merchant-1", name="M", status="ACTIVE"))
    session.add(Terminal(id="terminal-1", merchant_id="merchant-1", status="ACTIVE"))
    session.commit()
    return CLIENT_ID


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


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.decision.engine.LegalGraphBuilder.ensure_risk_decision_graph",
        lambda self, risk_decision: None,
    )
    monkeypatch.setattr(
        "app.services.transactions_service._validate_references",
        lambda *args, **kwargs: (
            SimpleNamespace(status="ACTIVE"),
            SimpleNamespace(status="ACTIVE"),
            SimpleNamespace(status="ACTIVE"),
            SimpleNamespace(status="ACTIVE"),
        ),
    )
    monkeypatch.setattr(
        "app.services.legal_integrations.service.LegalIntegrationsService.resolve_config",
        lambda self, tenant_id, client_id: SimpleNamespace(require_signature_for_finalize=False),
    )
    with scoped_session_context(tables=RISK_BLOCKING_TEST_TABLES) as db:
        yield db


def test_accounting_export_blocked_by_thresholds(session):
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
    with pytest.raises(AccountingExportRiskDeclined, match="risk_decline"):
        service.create_export(
            period_id=period.id,
            export_type=AccountingExportType.CHARGES,
            export_format=AccountingExportFormat.CSV,
            request_ctx=None,
            token=ADMIN_TOKEN,
        )


def test_payment_block_prevents_posting_and_audits(session):
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


def test_payout_block_prevents_export_and_audits(session):
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

    with pytest.raises(PayoutExportError, match="risk_decline"):
        create_payout_export(
            session,
            batch_id=batch.id,
            export_format=PayoutExportFormat.CSV,
            provider=None,
            external_ref=None,
            token=ADMIN_TOKEN,
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


def test_document_finalize_blocked_with_explain_and_audit(session):
    _seed_thresholds(
        session,
        threshold_set_id="document-block",
        subject_type=RiskSubjectType.DOCUMENT,
        action=RiskThresholdAction.DOCUMENT_FINALIZE,
    )
    document = Document(
        tenant_id=1,
        client_id="client-1",
        direction="INBOUND",
        title="Invoice",
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

    with router_client_context(
        router=admin_documents_router.router,
        prefix="/api/v1/admin",
        db_session=session,
        dependency_overrides={require_admin_user: lambda: dict(ADMIN_TOKEN)},
    ) as api_client:
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


def test_block_audit_links_to_explain(session):
    _seed_thresholds(
        session,
        threshold_set_id="payment-audit",
        subject_type=RiskSubjectType.PAYMENT,
        action=RiskThresholdAction.PAYMENT,
    )
    engine_instance = DecisionEngine(session)
    ctx = DecisionContext(
        tenant_id=1,
        client_id=CLIENT_ID,
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

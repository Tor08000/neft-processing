from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.accounting_export_batch import (
    AccountingExportBatch,
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import ClosingPackage, ClosingPackageStatus, Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.documents import DocumentDirection
from app.models.finance import InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.models.legal_graph import (
    LegalEdge,
    LegalEdgeType,
    LegalGraphSnapshot,
    LegalGraphSnapshotScopeType,
    LegalNode,
    LegalNodeType,
)
from app.models.risk_decision import RiskDecision
from app.services.legal_graph import GraphContext, LegalGraphBuilder, LegalGraphSnapshotService
from app.services.legal_graph.completeness import check_billing_period_completeness
from app.services.legal_graph.queries import trace
from app.services.legal_graph.registry import LegalGraphRegistry


LEGAL_GRAPH_TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    Invoice.__table__,
    Document.__table__,
    DocumentFile.__table__,
    ClosingPackage.__table__,
    DocumentAcknowledgement.__table__,
    InvoicePayment.__table__,
    InvoiceSettlementAllocation.__table__,
    AccountingExportBatch.__table__,
    RiskDecision.__table__,
    LegalNode.__table__,
    LegalEdge.__table__,
    LegalGraphSnapshot.__table__,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    stub_metadata = MetaData()

    def stub_metadata_table(name: str) -> Table:
        return Table(
            name,
            stub_metadata,
            Column("id", String(36), primary_key=True),
        )

    stub_metadata_table("clearing_batch")
    stub_metadata_table("reconciliation_requests")
    stub_metadata.create_all(bind=engine)
    for table in LEGAL_GRAPH_TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(LEGAL_GRAPH_TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine)
        engine.dispose()


def test_node_upsert_idempotent(session):
    registry = LegalGraphRegistry(session)
    first = registry.get_or_create_node(
        tenant_id=1,
        node_type=LegalNodeType.DOCUMENT,
        ref_id="doc-1",
    )
    second = registry.get_or_create_node(
        tenant_id=1,
        node_type=LegalNodeType.DOCUMENT,
        ref_id="doc-1",
    )

    assert first.node.id == second.node.id
    assert session.query(LegalNode).count() == 1


def test_edge_upsert_idempotent(session):
    registry = LegalGraphRegistry(session)
    src = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.DOCUMENT, ref_id="doc-1").node
    dst = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.INVOICE, ref_id="inv-1").node

    first = registry.link(tenant_id=1, src_node_id=src.id, dst_node_id=dst.id, edge_type=LegalEdgeType.GENERATED_FROM)
    second = registry.link(tenant_id=1, src_node_id=src.id, dst_node_id=dst.id, edge_type=LegalEdgeType.GENERATED_FROM)

    assert first.edge.id == second.edge.id
    assert session.query(LegalEdge).count() == 1


def test_snapshot_deterministic_hash(session):
    registry = LegalGraphRegistry(session)
    doc = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.DOCUMENT, ref_id="doc-1").node
    inv = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.INVOICE, ref_id="inv-1").node
    registry.link(tenant_id=1, src_node_id=doc.id, dst_node_id=inv.id, edge_type=LegalEdgeType.GENERATED_FROM)

    snapshots = LegalGraphSnapshotService(session)
    first = snapshots.create_snapshot(
        tenant_id=1,
        scope_type=LegalGraphSnapshotScopeType.DOCUMENT,
        scope_ref_id="doc-1",
        depth=3,
    )
    second = snapshots.create_snapshot(
        tenant_id=1,
        scope_type=LegalGraphSnapshotScopeType.DOCUMENT,
        scope_ref_id="doc-1",
        depth=3,
    )

    assert first.snapshot_hash == second.snapshot_hash
    assert first.nodes_count == 2
    assert first.edges_count == 1


def test_trace_query(session):
    registry = LegalGraphRegistry(session)
    node_a = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.DOCUMENT, ref_id="doc-a").node
    node_b = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.INVOICE, ref_id="inv-b").node
    node_c = registry.get_or_create_node(tenant_id=1, node_type=LegalNodeType.PAYMENT, ref_id="pay-c").node
    registry.link(tenant_id=1, src_node_id=node_a.id, dst_node_id=node_b.id, edge_type=LegalEdgeType.GENERATED_FROM)
    registry.link(tenant_id=1, src_node_id=node_b.id, dst_node_id=node_c.id, edge_type=LegalEdgeType.SETTLES)

    result = trace(session, tenant_id=1, node_type=LegalNodeType.DOCUMENT, ref_id="doc-a", depth=1)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert len(result.layers) == 2

    result = trace(session, tenant_id=1, node_type=LegalNodeType.DOCUMENT, ref_id="doc-a", depth=2)
    assert len(result.nodes) == 3
    assert len(result.edges) == 2


def test_graph_completeness_integration(session):
    period_date = date(2024, 5, 1)
    period = BillingPeriod(
        period_type=BillingPeriodType.MONTHLY,
        start_at=datetime.combine(period_date, time.min, tzinfo=timezone.utc),
        end_at=datetime.combine(period_date, time.max, tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.LOCKED,
    )
    session.add(period)
    session.flush()

    invoice = Invoice(
        client_id="client-1",
        period_from=period_date,
        period_to=period_date,
        currency="RUB",
        billing_period_id=period.id,
        total_amount=1000,
        tax_amount=0,
        total_with_tax=1000,
        amount_paid=0,
        amount_due=1000,
        status=InvoiceStatus.SENT,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.flush()

    invoice_doc = Document(
        tenant_id=1,
        client_id="client-1",
        direction=DocumentDirection.OUTBOUND,
        title="Invoice",
        document_type=DocumentType.INVOICE,
        period_from=period_date,
        period_to=period_date,
        status=DocumentStatus.FINALIZED,
        version=1,
        source_entity_type="invoice",
        source_entity_id=invoice.id,
        document_hash="hash-invoice",
    )
    act_doc = Document(
        tenant_id=1,
        client_id="client-1",
        direction=DocumentDirection.OUTBOUND,
        title="Act",
        document_type=DocumentType.ACT,
        period_from=period_date,
        period_to=period_date,
        status=DocumentStatus.FINALIZED,
        version=1,
        source_entity_type="billing_period",
        document_hash="hash-act",
    )
    recon_doc = Document(
        tenant_id=1,
        client_id="client-1",
        direction=DocumentDirection.OUTBOUND,
        title="Reconciliation act",
        document_type=DocumentType.RECONCILIATION_ACT,
        period_from=period_date,
        period_to=period_date,
        status=DocumentStatus.FINALIZED,
        version=1,
        source_entity_type="billing_period",
        document_hash="hash-recon",
    )
    session.add_all([invoice_doc, act_doc, recon_doc])
    session.flush()

    invoice_file = DocumentFile(
        document_id=invoice_doc.id,
        file_type=DocumentFileType.PDF,
        bucket="bucket",
        object_key="doc.pdf",
        sha256="file-hash",
        size_bytes=123,
        content_type="application/pdf",
    )
    session.add(invoice_file)
    session.flush()

    acknowledgement = DocumentAcknowledgement(
        tenant_id=1,
        client_id="client-1",
        document_type=invoice_doc.document_type.value,
        document_id=str(invoice_doc.id),
        document_object_key=invoice_file.object_key,
        document_hash=invoice_file.sha256,
        ack_by_user_id="user-1",
        ack_by_email="user@example.com",
        ack_method="UI",
        ack_ip="127.0.0.1",
        ack_user_agent="pytest",
        ack_at=datetime.now(timezone.utc),
    )
    session.add(acknowledgement)
    session.flush()

    package = ClosingPackage(
        tenant_id=1,
        client_id="client-1",
        period_from=period_date,
        period_to=period_date,
        status=ClosingPackageStatus.FINALIZED,
        version=1,
        invoice_document_id=invoice_doc.id,
        act_document_id=act_doc.id,
        recon_document_id=recon_doc.id,
    )
    session.add(package)
    session.flush()

    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=1000,
        currency="RUB",
        idempotency_key="pay-1",
    )
    session.add(payment)
    session.flush()

    allocation = InvoiceSettlementAllocation(
        invoice_id=invoice.id,
        tenant_id=1,
        client_id="client-1",
        settlement_period_id=period.id,
        source_type=SettlementSourceType.PAYMENT,
        source_id=str(payment.id),
        amount=1000,
        currency="RUB",
    )
    session.add(allocation)
    session.flush()

    export_batch = AccountingExportBatch(
        tenant_id=1,
        billing_period_id=period.id,
        export_type=AccountingExportType.CHARGES,
        format=AccountingExportFormat.CSV,
        state=AccountingExportState.CONFIRMED,
        idempotency_key="export-1",
    )
    session.add(export_batch)
    session.flush()

    graph_context = GraphContext(tenant_id=1)
    builder = LegalGraphBuilder(session, context=graph_context)
    builder.ensure_document_graph(invoice_doc)
    builder.ensure_document_graph(act_doc)
    builder.ensure_document_graph(recon_doc)
    builder.ensure_document_ack_graph(document=invoice_doc, acknowledgement=acknowledgement)
    builder.ensure_closing_package_graph(package)
    builder.ensure_settlement_allocation_graph(allocation, invoice=invoice, source=payment)
    builder.ensure_accounting_export_graph(export_batch)
    export_node = builder.registry.get_or_create_node(
        tenant_id=1,
        node_type=LegalNodeType.ACCOUNTING_EXPORT_BATCH,
        ref_id=str(export_batch.id),
        ref_table="accounting_export_batches",
    ).node
    period_node = builder.registry.get_or_create_node(
        tenant_id=1,
        node_type=LegalNodeType.BILLING_PERIOD,
        ref_id=str(period.id),
        ref_table="billing_periods",
    ).node
    builder.registry.link_edge(
        tenant_id=1,
        src_node_id=export_node.id,
        dst_node_id=period_node.id,
        edge_type=LegalEdgeType.CONFIRMS,
    )

    snapshot_service = LegalGraphSnapshotService(session)
    snapshot = snapshot_service.create_snapshot(
        tenant_id=1,
        scope_type=LegalGraphSnapshotScopeType.CLOSING_PACKAGE,
        scope_ref_id=str(package.id),
        depth=4,
    )

    result = check_billing_period_completeness(session, tenant_id=1, period_id=str(period.id))

    assert snapshot.snapshot_hash
    assert result.ok
    trace_result = trace(
        session,
        tenant_id=1,
        node_type=LegalNodeType.DOCUMENT,
        ref_id=str(invoice_doc.id),
        depth=2,
    )
    assert trace_result.nodes
    assert trace_result.edges

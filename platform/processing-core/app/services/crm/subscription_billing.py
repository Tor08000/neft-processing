from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobType
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.crm import (
    CRMBillingCycle,
    CRMFeatureFlagType,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
)
from app.models.documents import Document, DocumentStatus, DocumentType
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerTransaction
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLinkNodeType, MoneyFlowLinkType, MoneyInvariantSnapshotPhase
from app.services.audit_service import AuditService, RequestContext
from app.services.billing_job_runs import BillingJobRunService
from app.services.crm import events, repository
from app.services.crm.subscription_pricing_engine import price_subscription, price_subscription_v2
from app.services.crm.subscription_segments import ensure_segments_v2
from app.services.crm.subscription_usage_collector import collect_usage, collect_usage_by_segments
from app.services.internal_ledger import InternalLedgerService
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceStateMachine
from app.services.legal_graph.registry import LegalGraphRegistry
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.graph import MoneyFlowGraphBuilder, ensure_money_flow_links
from app.services.money_flow.snapshots import record_snapshot
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def run_subscription_billing(
    db: Session,
    *,
    billing_period_id: str,
    request_ctx: RequestContext | None = None,
) -> list[Invoice]:
    period = db.query(BillingPeriod).filter(BillingPeriod.id == billing_period_id).one_or_none()
    if not period:
        raise ValueError("billing period not found")

    subscriptions = repository.list_subscriptions(
        db,
        client_id=None,
        status=[CRMSubscriptionStatus.ACTIVE, CRMSubscriptionStatus.PAUSED],
        limit=1000,
    )
    job_service = BillingJobRunService(db)
    job_run = job_service.start(
        BillingJobType.SUBSCRIPTION_BILLING,
        params={"billing_period_id": str(period.id)},
        billing_period_id=str(period.id),
    )
    events.audit_event(
        db,
        event_type=events.SUBSCRIPTION_BILLING_RUN_STARTED,
        entity_type="billing_period",
        entity_id=str(period.id),
        payload={"subscriptions": len(subscriptions)},
        request_ctx=request_ctx,
    )
    invoices: list[Invoice] = []
    for subscription in subscriptions:
        try:
            with db.begin_nested():
                subscription_started_at = _as_utc(subscription.started_at)
                subscription_ended_at = _as_utc(subscription.ended_at)
                period_start = _as_utc(period.start_at)
                period_end = _as_utc(period.end_at)
                if subscription_started_at is not None and period_end is not None and subscription_started_at > period_end:
                    continue
                if subscription_ended_at is not None and period_start is not None and subscription_ended_at < period_start:
                    continue
                existing_charges = repository.list_subscription_charges(
                    db,
                    subscription_id=str(subscription.id),
                    billing_period_id=str(period.id),
                )
                if existing_charges:
                    continue
                segments = _ensure_subscription_segments(db, subscription=subscription, period=period)
                active_days = _active_days(segments)
                if active_days <= 0:
                    continue
                tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id)
                tariff_definition = _resolve_tariff_definition(tariff)
                included = tariff_definition.get("included") if isinstance(tariff_definition, dict) else {}
                fuel_flag = repository.get_feature_flag(
                    db,
                    tenant_id=subscription.tenant_id,
                    client_id=subscription.client_id,
                    feature=CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED,
                )
                include_fuel_metrics = bool(fuel_flag.enabled) if fuel_flag else False

                usage_result = collect_usage(
                    db,
                    subscription=subscription,
                    billing_period_id=str(period.id),
                    period_start=period_start or period.start_at,
                    period_end=period_end or period.end_at,
                    included=included,
                    include_fuel_metrics=include_fuel_metrics,
                )
                pricing_result = price_subscription(
                    subscription=subscription,
                    billing_period_id=str(period.id),
                    counters=usage_result.counters,
                    tariff_definition=tariff_definition,
                    segments=segments,
                    period_start=period_start or period.start_at,
                    period_end=period_end or period.end_at,
                )
                for counter in usage_result.counters:
                    repository.add_usage_counter(db, counter, auto_commit=False)
                events.audit_event(
                    db,
                    event_type=events.SUBSCRIPTION_CHARGES_COMPUTED,
                    entity_type="crm_subscription",
                    entity_id=str(subscription.id),
                    payload={"billing_period_id": str(period.id)},
                    request_ctx=request_ctx,
                )
                for charge in pricing_result.charges:
                    repository.add_subscription_charge(db, charge, auto_commit=False)
                    events.audit_event(
                        db,
                        event_type=events.CRM_SUBSCRIPTION_CHARGE_CREATED,
                        entity_type="crm_subscription_charge",
                        entity_id=str(charge.id),
                        payload={"subscription_id": str(subscription.id), "code": charge.code},
                        request_ctx=request_ctx,
                    )

                invoice = _create_subscription_invoice(
                    db,
                    subscription_id=str(subscription.id),
                    client_id=subscription.client_id,
                    billing_period_id=str(period.id),
                    period_from=period.start_at.date(),
                    period_to=period.end_at.date(),
                    charges=pricing_result.charges,
                    currency=_resolve_currency(tariff_definition),
                    tenant_id=subscription.tenant_id,
                    request_ctx=request_ctx,
                )
                invoices.append(invoice)
                events.audit_event(
                    db,
                    event_type=events.SUBSCRIPTION_INVOICE_CREATED,
                    entity_type="invoice",
                    entity_id=invoice.id,
                    payload={"subscription_id": str(subscription.id), "billing_period_id": str(period.id)},
                    request_ctx=request_ctx,
                )

                documents = _create_subscription_documents(
                    db,
                    tenant_id=subscription.tenant_id,
                    subscription_id=str(subscription.id),
                    invoice=invoice,
                    period_from=period.start_at.date(),
                    period_to=period.end_at.date(),
                    request_ctx=request_ctx,
                )
                _ensure_money_flow_links(
                    db,
                    subscription_id=str(subscription.id),
                    billing_period_id=str(period.id),
                    segments=segments,
                    counters=usage_result.counters,
                    charges=pricing_result.charges,
                    invoice=invoice,
                    documents=documents,
                    client_id=subscription.client_id,
                    tenant_id=subscription.tenant_id,
                )
                _record_invoice_snapshots(
                    db,
                    subscription_id=str(subscription.id),
                    billing_period_id=str(period.id),
                    invoice=invoice,
                    charges=pricing_result.charges,
                    client_id=subscription.client_id,
                    tenant_id=subscription.tenant_id,
                )
                events.audit_event(
                    db,
                    event_type=events.CRM_SUBSCRIPTION_BILLED,
                    entity_type="crm_subscription",
                    entity_id=str(subscription.id),
                    payload={"billing_period_id": str(period.id), "invoice_id": invoice.id},
                    request_ctx=request_ctx,
                )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            AuditService(db).audit(
                event_type="SUBSCRIPTION_BILLING_FAILED",
                entity_type="crm_subscription",
                entity_id=str(subscription.id),
                action="FAILED",
                after={"error": str(exc), "billing_period_id": str(period.id)},
                request_ctx=request_ctx,
            )
            job_service.fail(job_run, error=str(exc))
            raise

    events.audit_event(
        db,
        event_type=events.SUBSCRIPTION_BILLING_RUN_COMPLETED,
        entity_type="billing_period",
        entity_id=str(period.id),
        payload={"invoices": [invoice.id for invoice in invoices]},
        request_ctx=request_ctx,
    )
    metrics = {"subscriptions": len(subscriptions), "invoices": len(invoices)}
    job_service.succeed(job_run, metrics=metrics)
    return invoices


def run_subscription_billing_v2(
    db: Session,
    *,
    billing_period_id: str,
    request_ctx: RequestContext | None = None,
) -> list[Invoice]:
    period = db.query(BillingPeriod).filter(BillingPeriod.id == billing_period_id).one_or_none()
    if not period:
        raise ValueError("billing period not found")

    subscriptions = repository.list_subscriptions(
        db,
        client_id=None,
        status=[CRMSubscriptionStatus.ACTIVE, CRMSubscriptionStatus.PAUSED],
        limit=1000,
    )
    invoices: list[Invoice] = []
    for subscription in subscriptions:
        tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id)
        tariff_definition = _resolve_tariff_definition(tariff)
        if tariff_definition.get("version") != 2:
            continue
        subscription_started_at = _as_utc(subscription.started_at)
        subscription_ended_at = _as_utc(subscription.ended_at)
        period_start = _as_utc(period.start_at)
        period_end = _as_utc(period.end_at)
        if subscription_started_at is not None and period_end is not None and subscription_started_at > period_end:
            continue
        if subscription_ended_at is not None and period_start is not None and subscription_ended_at < period_start:
            continue
        with db.begin_nested():
            segments = ensure_segments_v2(db, subscription=subscription, period=period)
            if not segments:
                continue
            fuel_flag = repository.get_feature_flag(
                db,
                tenant_id=subscription.tenant_id,
                client_id=subscription.client_id,
                feature=CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED,
            )
            include_fuel_metrics = bool(fuel_flag.enabled) if fuel_flag else False
            counters = collect_usage_by_segments(
                db,
                subscription=subscription,
                billing_period_id=str(period.id),
                segments=segments,
                include_fuel_metrics=include_fuel_metrics,
            ).counters
            pricing_result = price_subscription_v2(
                subscription=subscription,
                billing_period_id=str(period.id),
                segments=segments,
                counters=counters,
                tariff_definition=tariff_definition,
                period_start=period_start or period.start_at,
                period_end=period_end or period.end_at,
            )
            _persist_usage_counters(
                db,
                subscription_id=str(subscription.id),
                billing_period_id=str(period.id),
                counters=counters,
            )
            charges = _persist_charges_v2(
                db,
                subscription_id=str(subscription.id),
                billing_period_id=str(period.id),
                charges=pricing_result.charges,
            )
            invoice = _create_subscription_invoice_v2(
                db,
                subscription_id=str(subscription.id),
                client_id=subscription.client_id,
                billing_period_id=str(period.id),
                period_from=period.start_at.date(),
                period_to=period.end_at.date(),
                charges=charges,
                currency=_resolve_currency(tariff_definition),
                tenant_id=subscription.tenant_id,
                request_ctx=request_ctx,
            )
            invoices.append(invoice)
            documents = _create_subscription_documents(
                db,
                tenant_id=subscription.tenant_id,
                subscription_id=str(subscription.id),
                invoice=invoice,
                period_from=period.start_at.date(),
                period_to=period.end_at.date(),
                request_ctx=request_ctx,
            )
            _ensure_money_flow_links(
                db,
                subscription_id=str(subscription.id),
                billing_period_id=str(period.id),
                segments=segments,
                counters=counters,
                charges=charges,
                invoice=invoice,
                documents=documents,
                client_id=subscription.client_id,
                tenant_id=subscription.tenant_id,
            )
            _record_invoice_snapshots(
                db,
                subscription_id=str(subscription.id),
                billing_period_id=str(period.id),
                invoice=invoice,
                charges=charges,
                client_id=subscription.client_id,
                tenant_id=subscription.tenant_id,
            )
        db.commit()
    return invoices


def _create_subscription_invoice(
    db: Session,
    *,
    subscription_id: str,
    client_id: str,
    billing_period_id: str,
    period_from,
    period_to,
    charges,
    currency: str,
    tenant_id: int,
    request_ctx: RequestContext | None,
) -> Invoice:
    idempotency_key = f"subscription:{subscription_id}:period:{billing_period_id}:v1"
    invoice = (
        db.query(Invoice)
        .filter(Invoice.external_number == idempotency_key)
        .one_or_none()
    )
    if invoice is None:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.billing_period_id == billing_period_id)
            .filter(Invoice.currency == currency)
            .one_or_none()
        )
    if invoice:
        return invoice
    invoice = Invoice(
        client_id=client_id,
        period_from=period_from,
        period_to=period_to,
        currency=currency,
        billing_period_id=billing_period_id,
        status=InvoiceStatus.DRAFT,
        external_number=idempotency_key,
    )
    db.add(invoice)
    db.flush()
    lines = []
    for charge in charges:
        lines.append(
            InvoiceLine(
                invoice_id=invoice.id,
                operation_id=f"subscription:{subscription_id}:{charge.code}",
                product_id=charge.code,
                liters=None,
                unit_price=charge.unit_price,
                line_amount=charge.amount,
                tax_amount=0,
            )
        )
    invoice.lines = lines
    invoice.total_amount = sum(int(line.line_amount or 0) for line in lines)
    invoice.tax_amount = 0
    invoice.total_with_tax = invoice.total_amount
    invoice.amount_due = invoice.total_amount
    db.add(invoice)
    try:
        InvoiceStateMachine(invoice, db=db).transition(
            to=InvoiceStatus.ISSUED,
            actor="subscription_billing",
            reason="subscription_billing",
            request_ctx=request_ctx,
        )
        events.audit_event(
            db,
            event_type=events.SUBSCRIPTION_INVOICE_ISSUED,
            entity_type="invoice",
            entity_id=invoice.id,
            payload={"subscription_id": subscription_id, "billing_period_id": billing_period_id},
            request_ctx=request_ctx,
        )
    except InvalidTransitionError as exc:
        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.now(timezone.utc)
        db.add(invoice)
        AuditService(db).audit(
            event_type="SUBSCRIPTION_INVOICE_REVIEW_REQUIRED",
            entity_type="invoice",
            entity_id=invoice.id,
            action="REVIEW_REQUIRED",
            after={"reason": str(exc)},
            request_ctx=request_ctx,
        )
    db.flush()
    InternalLedgerService(db).post_invoice_issued(invoice=invoice, tenant_id=tenant_id)
    return invoice


def _create_subscription_invoice_v2(
    db: Session,
    *,
    subscription_id: str,
    client_id: str,
    billing_period_id: str,
    period_from,
    period_to,
    charges,
    currency: str,
    tenant_id: int,
    request_ctx: RequestContext | None,
) -> Invoice:
    idempotency_key = f"subscription:{subscription_id}:period:{billing_period_id}:v2"
    invoice = db.query(Invoice).filter(Invoice.external_number == idempotency_key).one_or_none()
    if invoice:
        return invoice
    invoice = Invoice(
        client_id=client_id,
        period_from=period_from,
        period_to=period_to,
        currency=currency,
        billing_period_id=billing_period_id,
        status=InvoiceStatus.DRAFT,
        external_number=idempotency_key,
    )
    db.add(invoice)
    db.flush()
    lines = []
    for charge in charges:
        operation_id = charge.charge_key or f"subscription:{subscription_id}:{charge.code}"
        lines.append(
            InvoiceLine(
                invoice_id=invoice.id,
                operation_id=operation_id,
                product_id=charge.code,
                liters=None,
                unit_price=charge.unit_price,
                line_amount=charge.amount,
                tax_amount=0,
            )
        )
    invoice.lines = lines
    invoice.total_amount = sum(int(line.line_amount or 0) for line in lines)
    invoice.tax_amount = 0
    invoice.total_with_tax = invoice.total_amount
    invoice.amount_due = invoice.total_amount
    db.add(invoice)
    try:
        InvoiceStateMachine(invoice, db=db).transition(
            to=InvoiceStatus.ISSUED,
            actor="subscription_billing_v2",
            reason="subscription_billing_v2",
            request_ctx=request_ctx,
        )
    except InvalidTransitionError:
        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.now(timezone.utc)
        db.add(invoice)
    db.flush()
    InternalLedgerService(db).post_invoice_issued(invoice=invoice, tenant_id=tenant_id)
    return invoice


def _create_subscription_documents(
    db: Session,
    *,
    tenant_id: int,
    subscription_id: str,
    invoice: Invoice,
    period_from,
    period_to,
    request_ctx: RequestContext | None,
) -> list[Document]:
    existing = (
        db.query(Document)
        .filter(Document.client_id == invoice.client_id)
        .filter(Document.period_from == period_from)
        .filter(Document.period_to == period_to)
        .filter(Document.document_type.in_([DocumentType.SUBSCRIPTION_INVOICE, DocumentType.SUBSCRIPTION_ACT]))
        .all()
    )
    if existing:
        return existing
    generated_at = datetime.now(timezone.utc)
    invoice_doc_id = str(uuid4())
    act_doc_id = str(uuid4())
    db.execute(
        Document.__table__.insert(),
        [
            {
                "id": invoice_doc_id,
                "tenant_id": tenant_id,
                "client_id": invoice.client_id,
                "direction": "OUTBOUND",
                "title": "Subscription invoice",
                "document_type": DocumentType.SUBSCRIPTION_INVOICE.value,
                "period_from": period_from,
                "period_to": period_to,
                "version": 1,
                "status": DocumentStatus.ISSUED.value,
                "created_at": generated_at,
                "generated_at": generated_at,
                "sender_type": "NEFT",
                "source_entity_type": "invoice",
                "source_entity_id": invoice.id,
                "number": invoice.number,
            },
            {
                "id": act_doc_id,
                "tenant_id": tenant_id,
                "client_id": invoice.client_id,
                "direction": "OUTBOUND",
                "title": "Subscription act",
                "document_type": DocumentType.SUBSCRIPTION_ACT.value,
                "period_from": period_from,
                "period_to": period_to,
                "version": 1,
                "status": DocumentStatus.ISSUED.value,
                "created_at": generated_at,
                "generated_at": generated_at,
                "sender_type": "NEFT",
                "source_entity_type": "subscription",
                "source_entity_id": subscription_id,
                "number": None,
            },
        ],
    )
    documents = (
        db.query(Document)
        .filter(Document.id.in_([invoice_doc_id, act_doc_id]))
        .all()
    )
    documents_by_type = {document.document_type: document for document in documents}
    invoice_doc = documents_by_type[DocumentType.SUBSCRIPTION_INVOICE]
    act_doc = documents_by_type[DocumentType.SUBSCRIPTION_ACT]
    registry = LegalGraphRegistry(db, request_ctx=request_ctx)
    sub_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.SUBSCRIPTION,
        ref_id=subscription_id,
        ref_table="crm_subscriptions",
    ).node
    invoice_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.INVOICE,
        ref_id=invoice.id,
        ref_table="invoices",
    ).node
    invoice_doc_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.DOCUMENT,
        ref_id=str(invoice_doc.id),
        ref_table="documents",
    ).node
    act_doc_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.DOCUMENT,
        ref_id=str(act_doc.id),
        ref_table="documents",
    ).node
    registry.link(
        tenant_id=tenant_id,
        src_node_id=sub_node.id,
        dst_node_id=invoice_node.id,
        edge_type=LegalEdgeType.GENERATED_FROM,
    )
    billing_node = registry.get_or_create_node(
        tenant_id=tenant_id,
        node_type=LegalNodeType.BILLING_PERIOD,
        ref_id=str(invoice.billing_period_id),
        ref_table="billing_periods",
    ).node
    registry.link(
        tenant_id=tenant_id,
        src_node_id=invoice_doc_node.id,
        dst_node_id=billing_node.id,
        edge_type=LegalEdgeType.INCLUDES,
    )
    registry.link(
        tenant_id=tenant_id,
        src_node_id=act_doc_node.id,
        dst_node_id=billing_node.id,
        edge_type=LegalEdgeType.INCLUDES,
    )
    return [invoice_doc, act_doc]


def _resolve_currency(tariff_definition: dict | None) -> str:
    if isinstance(tariff_definition, dict):
        base_fee = tariff_definition.get("base_fee") or {}
        currency = base_fee.get("currency")
        if currency:
            return currency
    return "RUB"


def _resolve_tariff_definition(tariff) -> dict:
    if tariff is None:
        return {}
    if isinstance(tariff.definition, dict):
        return tariff.definition
    return {
        "base_fee": {"amount_minor": tariff.base_fee_minor, "currency": tariff.currency},
        "included": {},
        "overage": {},
        "domains": _normalize_domains(tariff.features),
        "risk_profile_id": None,
        "limit_profile_id": None,
        "version": 1,
    }


def _persist_usage_counters(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    counters,
) -> None:
    existing = repository.list_usage_counters(
        db,
        subscription_id=subscription_id,
        billing_period_id=billing_period_id,
    )
    existing_keys = {(str(counter.segment_id), counter.metric.value) for counter in existing}
    for counter in counters:
        key = (str(counter.segment_id), counter.metric.value)
        if key in existing_keys:
            continue
        repository.add_usage_counter(db, counter, auto_commit=False)


def _persist_charges_v2(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    charges,
) -> list:
    persisted = []
    for charge in charges:
        if charge.charge_key:
            existing = repository.get_subscription_charge_by_key(
                db,
                subscription_id=subscription_id,
                billing_period_id=billing_period_id,
                charge_key=charge.charge_key,
            )
            if existing:
                persisted.append(existing)
                continue
        repository.add_subscription_charge(db, charge, auto_commit=False)
        persisted.append(charge)
    return persisted


def _ensure_money_flow_links(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    segments: list[CRMSubscriptionPeriodSegment],
    counters,
    charges,
    invoice: Invoice,
    documents: list[Document],
    client_id: str,
    tenant_id: int,
) -> None:
    builder = MoneyFlowGraphBuilder(tenant_id=tenant_id, client_id=client_id)
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.SUBSCRIPTION,
        src_id=subscription_id,
        link_type=MoneyFlowLinkType.RELATES,
        dst_type=MoneyFlowLinkNodeType.BILLING_PERIOD,
        dst_id=billing_period_id,
        meta={"billing_period_id": billing_period_id},
    )
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.SUBSCRIPTION,
        src_id=subscription_id,
        link_type=MoneyFlowLinkType.GENERATES,
        dst_type=MoneyFlowLinkNodeType.INVOICE,
        dst_id=invoice.id,
        meta={"billing_period_id": billing_period_id},
    )
    for segment in segments:
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.SUBSCRIPTION,
            src_id=subscription_id,
            link_type=MoneyFlowLinkType.GENERATES,
            dst_type=MoneyFlowLinkNodeType.SUBSCRIPTION_SEGMENT,
            dst_id=str(segment.id),
            meta={
                "segment_start": segment.segment_start.isoformat(),
                "segment_end": segment.segment_end.isoformat(),
                "tariff_id": segment.tariff_plan_id,
                "status": segment.status.value,
                "reason": segment.reason.value if segment.reason else None,
            },
        )
    counters_by_segment = {str(counter.segment_id): [] for counter in counters if counter.segment_id}
    for counter in counters:
        if not counter.segment_id:
            continue
        counters_by_segment.setdefault(str(counter.segment_id), []).append(counter)
    for segment in segments:
        for counter in counters_by_segment.get(str(segment.id), []):
            builder.add_link(
                src_type=MoneyFlowLinkNodeType.SUBSCRIPTION_SEGMENT,
                src_id=str(segment.id),
                link_type=MoneyFlowLinkType.GENERATES,
                dst_type=MoneyFlowLinkNodeType.USAGE_COUNTER,
                dst_id=str(counter.id),
                meta={
                    "metric": counter.metric.value,
                    "value": int(counter.value),
                    "limit_value": int(counter.limit_value) if counter.limit_value is not None else None,
                    "overage": int(counter.overage) if counter.overage is not None else None,
                },
            )
    charges_by_segment: dict[str, list] = {}
    for charge in charges:
        if not charge.segment_id:
            continue
        charges_by_segment.setdefault(str(charge.segment_id), []).append(charge)
    for segment in segments:
        for charge in charges_by_segment.get(str(segment.id), []):
            builder.add_link(
                src_type=MoneyFlowLinkNodeType.SUBSCRIPTION_SEGMENT,
                src_id=str(segment.id),
                link_type=MoneyFlowLinkType.GENERATES,
                dst_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
                dst_id=str(charge.id),
                meta={
                    "charge_key": charge.charge_key,
                    "charge_type": charge.charge_type.value,
                    "code": charge.code,
                    "amount": int(charge.amount),
                    "quantity": int(charge.quantity),
                    "unit_price": int(charge.unit_price),
                    "currency": charge.currency,
                    "explain": charge.explain,
                },
            )
            builder.add_link(
                src_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
                src_id=str(charge.id),
                link_type=MoneyFlowLinkType.GENERATES,
                dst_type=MoneyFlowLinkNodeType.INVOICE,
                dst_id=invoice.id,
                meta={"charge_key": charge.charge_key, "code": charge.code},
            )
    for charge in charges:
        if charge.segment_id:
            continue
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE,
            src_id=str(charge.id),
            link_type=MoneyFlowLinkType.GENERATES,
            dst_type=MoneyFlowLinkNodeType.INVOICE,
            dst_id=invoice.id,
            meta={"charge_key": charge.charge_key, "code": charge.code},
        )
    for document in documents:
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.INVOICE,
            src_id=invoice.id,
            link_type=MoneyFlowLinkType.GENERATES,
            dst_type=MoneyFlowLinkNodeType.DOCUMENT,
            dst_id=str(document.id),
            meta={"document_type": document.document_type.value},
        )

    ledger_tx = _fetch_invoice_ledger_transaction(db, invoice_id=invoice.id)
    if ledger_tx:
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.INVOICE,
            src_id=invoice.id,
            link_type=MoneyFlowLinkType.POSTS,
            dst_type=MoneyFlowLinkNodeType.LEDGER_TX,
            dst_id=str(ledger_tx.id),
            meta={"ledger_transaction_id": str(ledger_tx.id)},
        )
    ensure_money_flow_links(db, tenant_id=tenant_id, client_id=client_id, links=builder.build())


def _fetch_invoice_ledger_transaction(db: Session, *, invoice_id: str) -> InternalLedgerTransaction | None:
    return (
        db.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "INVOICE")
        .filter(InternalLedgerTransaction.external_ref_id == invoice_id)
        .one_or_none()
    )


def _build_invoice_snapshot_payload(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    invoice: Invoice,
    charges,
) -> dict[str, object]:
    ledger_tx = _fetch_invoice_ledger_transaction(db, invoice_id=invoice.id)
    balanced = None
    ledger_entries = []
    if ledger_tx:
        entries = (
            db.query(InternalLedgerEntry)
            .filter(InternalLedgerEntry.ledger_transaction_id == ledger_tx.id)
            .all()
        )
        debit_total = sum(entry.amount for entry in entries if entry.direction.value == "DEBIT")
        credit_total = sum(entry.amount for entry in entries if entry.direction.value == "CREDIT")
        balanced = debit_total == credit_total
        ledger_entries = [
            {
                "direction": entry.direction.value,
                "amount": int(entry.amount),
                "currency": entry.currency,
                "account_id": entry.account_id,
            }
            for entry in entries
        ]
    charges_total = sum(int(charge.amount) for charge in charges)
    return {
        "action": "ISSUE_INVOICE",
        "subscription_id": subscription_id,
        "period": {"billing_period_id": billing_period_id},
        "invoice": {
            "id": invoice.id,
            "status": invoice.status.value,
            "total_with_tax": int(invoice.total_with_tax or 0),
            "amount_paid": int(invoice.amount_paid or 0),
            "amount_due": int(invoice.amount_due or 0),
            "amount_refunded": int(invoice.amount_refunded or 0),
        },
        "charges": {"count": len(charges), "total_amount": charges_total},
        "ledger": {
            "transaction_id": str(ledger_tx.id) if ledger_tx else None,
            "balanced": balanced,
            "entries": ledger_entries,
        },
    }


def _record_invoice_snapshots(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    invoice: Invoice,
    charges,
    client_id: str,
    tenant_id: int,
) -> None:
    event = _ensure_money_flow_event(
        db,
        subscription_id=subscription_id,
        period_id=billing_period_id,
        invoice_id=invoice.id,
        client_id=client_id,
        tenant_id=tenant_id,
    )
    snapshot_payload = _build_invoice_snapshot_payload(
        db,
        subscription_id=subscription_id,
        billing_period_id=billing_period_id,
        invoice=invoice,
        charges=charges,
    )
    record_snapshot(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        flow_type=MoneyFlowType.SUBSCRIPTION_CHARGE,
        flow_ref_id=invoice.id,
        event_id=str(event.id),
        phase=MoneyInvariantSnapshotPhase.BEFORE,
        snapshot_json=snapshot_payload,
    )
    record_snapshot(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        flow_type=MoneyFlowType.SUBSCRIPTION_CHARGE,
        flow_ref_id=invoice.id,
        event_id=str(event.id),
        phase=MoneyInvariantSnapshotPhase.AFTER,
        snapshot_json=snapshot_payload,
    )


def _ensure_money_flow_event(
    db: Session,
    *,
    subscription_id: str,
    period_id: str,
    invoice_id: str,
    client_id: str,
    tenant_id: int,
) -> MoneyFlowEvent:
    idempotency_key = f"money:subscription:{subscription_id}:period:{period_id}:invoice:{invoice_id}:v2"
    existing = db.query(MoneyFlowEvent).filter(MoneyFlowEvent.idempotency_key == idempotency_key).one_or_none()
    if existing:
        return existing
    event = MoneyFlowEvent(
        tenant_id=tenant_id,
        client_id=client_id,
        flow_type=MoneyFlowType.SUBSCRIPTION_CHARGE,
        flow_ref_id=invoice_id,
        state_from=None,
        state_to=MoneyFlowState.AUTHORIZED,
        event_type=MoneyFlowEventType.AUTHORIZE,
        idempotency_key=idempotency_key,
        meta={"subscription_id": subscription_id, "billing_period_id": period_id},
    )
    db.add(event)
    db.flush()
    return event


def _normalize_domains(features: dict | None) -> dict:
    features = features or {}
    return {
        "fuel_enabled": bool(features.get("fuel")),
        "logistics_enabled": bool(features.get("logistics")),
        "documents_enabled": bool(features.get("docs") or features.get("documents")),
        "accounting_export_enabled": bool(features.get("export") or features.get("accounting")),
        "risk_blocking_enabled": bool(features.get("risk")),
    }


def run_subscription_billing_job(
    db: Session,
    *,
    today: date | None = None,
    request_ctx: RequestContext | None = None,
) -> list[Invoice]:
    today = today or datetime.now(timezone.utc).date()
    subscriptions = repository.list_subscriptions(
        db,
        client_id=None,
        status=[CRMSubscriptionStatus.ACTIVE, CRMSubscriptionStatus.PAUSED],
        limit=1000,
    )
    invoices: list[Invoice] = []
    period_ids: set[str] = set()
    for subscription in subscriptions:
        if subscription.billing_cycle != CRMBillingCycle.MONTHLY:
            continue
        if subscription.billing_day != today.day:
            continue
        period = resolve_subscription_billing_period(db, subscription=subscription, today=today)
        period_ids.add(str(period.id))
    for period_id in period_ids:
        invoices.extend(run_subscription_billing(db, billing_period_id=period_id, request_ctx=request_ctx))
    return invoices


def resolve_subscription_billing_period(
    db: Session,
    *,
    subscription,
    today: date,
) -> BillingPeriod:
    start, end = _previous_month_bounds(today)
    period = (
        db.query(BillingPeriod)
        .filter(BillingPeriod.period_type == BillingPeriodType.MONTHLY)
        .filter(BillingPeriod.start_at == start)
        .filter(BillingPeriod.end_at == end)
        .one_or_none()
    )
    if period:
        return period
    period = BillingPeriod(
        period_type=BillingPeriodType.MONTHLY,
        start_at=start,
        end_at=end,
        tz="UTC",
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def _previous_month_bounds(today: date) -> tuple[datetime, datetime]:
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - timedelta(days=1)
    start_prev_month = last_prev_month.replace(day=1)
    start_at = datetime(start_prev_month.year, start_prev_month.month, 1, tzinfo=timezone.utc)
    end_at = datetime(last_prev_month.year, last_prev_month.month, last_prev_month.day, 23, 59, 59, tzinfo=timezone.utc)
    return start_at, end_at


def _ensure_subscription_segments(
    db: Session,
    *,
    subscription,
    period: BillingPeriod,
) -> list[CRMSubscriptionPeriodSegment]:
    existing = repository.list_subscription_segments(
        db,
        subscription_id=str(subscription.id),
        billing_period_id=str(period.id),
    )
    if existing:
        return existing
    segments = _build_subscription_segments(subscription=subscription, period=period)
    for segment in segments:
        repository.add_subscription_segment(db, segment, auto_commit=False)
    return segments


def _build_subscription_segments(*, subscription, period: BillingPeriod) -> list[CRMSubscriptionPeriodSegment]:
    segments: list[CRMSubscriptionPeriodSegment] = []
    period_start = _as_utc(period.start_at)
    period_end = _as_utc(period.end_at)
    started_at = _as_utc(subscription.started_at)
    ended_at = _as_utc(subscription.ended_at)
    paused_at = _as_utc(subscription.paused_at)
    active_start = max(started_at, period_start)
    active_end = period_end
    if ended_at:
        active_end = min(active_end, ended_at)
    if subscription.status == CRMSubscriptionStatus.PAUSED and paused_at:
        active_end = min(active_end, paused_at)
    if active_start <= active_end:
        segments.append(
            CRMSubscriptionPeriodSegment(
                subscription_id=subscription.id,
                billing_period_id=period.id,
                tariff_plan_id=subscription.tariff_plan_id,
                segment_start=active_start,
                segment_end=active_end,
                status=CRMSubscriptionSegmentStatus.ACTIVE,
                days_count=_count_days(active_start, active_end),
            )
        )
    if subscription.status == CRMSubscriptionStatus.PAUSED and paused_at:
        paused_start = max(paused_at, period_start)
        paused_end = period_end
        if ended_at:
            paused_end = min(paused_end, ended_at)
        if paused_start <= paused_end:
            segments.append(
                CRMSubscriptionPeriodSegment(
                    subscription_id=subscription.id,
                    billing_period_id=period.id,
                    tariff_plan_id=subscription.tariff_plan_id,
                    segment_start=paused_start,
                    segment_end=paused_end,
                    status=CRMSubscriptionSegmentStatus.PAUSED,
                    days_count=_count_days(paused_start, paused_end),
                )
            )
    return segments


def _count_days(start_at: datetime, end_at: datetime) -> int:
    return (end_at.date() - start_at.date()).days + 1


def _active_days(segments: list[CRMSubscriptionPeriodSegment]) -> int:
    return sum(segment.days_count for segment in segments if segment.status == CRMSubscriptionSegmentStatus.ACTIVE)


__all__ = [
    "resolve_subscription_billing_period",
    "run_subscription_billing",
    "run_subscription_billing_v2",
    "run_subscription_billing_job",
]

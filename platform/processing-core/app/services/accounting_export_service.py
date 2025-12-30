from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.accounting_export_batch import (
    AccountingExportBatch,
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)
from app.models.erp_exports import ErpExportProfile, ErpMappingStatus, ErpSystemType
from app.models.audit_log import AuditVisibility
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.models.risk_score import RiskScoreAction
from app.services.accounting_export.canonical import AccountingEntry
from app.services.accounting_export.delivery import DeliveryPayload, build_delivery_adapter
from app.services.accounting_export.formats.csv_1c import serialize_charges_csv, serialize_settlement_csv
from app.services.accounting_export.formats.json_sap import serialize_sap_json
from app.services.accounting_export.erp_mapping_service import ErpMappingNotFound, ErpMappingService
from app.services.accounting_export.mappers import map_charges_entries, map_settlement_entries
from app.services.accounting_export.onboarding_profiles import get_onboarding_profile
from app.services.accounting_export.serializer import serialize_metadata_json
from app.services.audit_service import AuditService, RequestContext
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.policy import Action, PolicyAccessDenied, PolicyEngine, actor_from_token, audit_access_denied
from app.services.policy.resources import ResourceContext
from app.services.s3_storage import S3Storage
from app.services.legal_graph import (
    GraphContext,
    LegalGraphBuilder,
    LegalGraphWriteFailure,
    audit_graph_write_failure,
)
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


class AccountingExportError(RuntimeError):
    """Base error for accounting exports."""


class AccountingExportForbidden(AccountingExportError):
    """Raised when export is attempted for open billing periods."""


class AccountingExportNotFound(AccountingExportError):
    """Raised when export batch is missing."""


class AccountingExportInvalidState(AccountingExportError):
    """Raised when export cannot be processed due to its state."""


class AccountingExportRiskDeclined(AccountingExportError):
    """Raised when export is declined by risk scoring."""


@dataclass(frozen=True)
class AccountingExportPayload:
    payload: bytes
    records_count: int


class AccountingExportService:
    def __init__(self, db: Session):
        self.db = db
        self.policy_engine = PolicyEngine()

    def create_export(
        self,
        *,
        period_id: str,
        export_type: AccountingExportType,
        export_format: AccountingExportFormat,
        profile_id: str | None = None,
        system_type: ErpSystemType | None = None,
        request_ctx: RequestContext | None,
        version: int = 1,
        force: bool = False,
        token: dict | None = None,
    ) -> AccountingExportBatch:
        period = self._load_period(period_id)
        actor = actor_from_token(token)
        resource = ResourceContext(
            resource_type="ACCOUNTING_EXPORT",
            tenant_id=actor.tenant_id,
            client_id=None,
            status=period.status.value if period.status else None,
        )
        decision_context = DecisionContext(
            tenant_id=actor.tenant_id or 0,
            client_id=actor.client_id or actor.user_id or f"tenant-{actor.tenant_id}",
            actor_type="ADMIN",
            action=DecisionAction.ACCOUNTING_EXPORT,
            amount=0,
            billing_period_id=str(period.id),
            history={},
            metadata={
                "billing_period_status": period.status.value if period.status else None,
                "actor_roles": actor.roles,
                "subject_id": str(period.id),
            },
        )
        decision = DecisionEngine(self.db).evaluate(decision_context)
        if decision.outcome != DecisionOutcome.ALLOW:
            reason = "manual_review_required" if decision.outcome == DecisionOutcome.MANUAL_REVIEW else "risk_decline"
            raise AccountingExportRiskDeclined(reason)
        policy_decision = self.policy_engine.check(
            actor=actor,
            action=Action.ACCOUNTING_EXPORT_CREATE,
            resource=resource,
        )
        if not policy_decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=Action.ACCOUNTING_EXPORT_CREATE,
                resource=resource,
                decision=policy_decision,
                token=token,
            )
            raise PolicyAccessDenied(policy_decision)
        self._require_period_finalized(period, request_ctx=request_ctx)

        profile = self._load_profile(profile_id) if profile_id else None
        export_format = self._resolve_export_format(export_format, profile=profile)
        idempotency_key = self._build_idempotency_key(
            period_id=period_id,
            export_type=export_type,
            export_format=export_format,
            version=version,
            profile_id=str(profile.id) if profile else None,
            mapping_version=profile.mapping.version if profile and profile.mapping else None,
        )
        existing = (
            self.db.query(AccountingExportBatch)
            .filter(AccountingExportBatch.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            if existing.state == AccountingExportState.FAILED and force:
                self._reset_failed_batch(existing)
                self.db.flush()
            return existing

        batch = AccountingExportBatch(
            tenant_id=self._resolve_tenant_id(request_ctx),
            billing_period_id=period_id,
            export_type=export_type,
            format=export_format,
            state=AccountingExportState.CREATED,
            idempotency_key=idempotency_key,
            erp_profile_id=str(profile.id) if profile else None,
            erp_system_type=profile.system_type if profile else system_type,
            erp_mapping_id=str(profile.mapping.id) if profile and profile.mapping else None,
            erp_mapping_version=profile.mapping.version if profile and profile.mapping else None,
        )
        self.db.add(batch)
        self.db.flush()

        self._audit_event(
            event_type="ACCOUNTING_EXPORT_CREATED",
            batch=batch,
            request_ctx=request_ctx,
        )
        return batch

    def generate_export(
        self,
        *,
        batch_id: str,
        request_ctx: RequestContext | None,
        force: bool = False,
        token: dict | None = None,
    ) -> AccountingExportBatch:
        batch = self._load_batch(batch_id)
        if batch.state in {
            AccountingExportState.GENERATED,
            AccountingExportState.UPLOADED,
            AccountingExportState.DOWNLOADED,
            AccountingExportState.CONFIRMED,
        } and not force:
            return batch
        if batch.state == AccountingExportState.FAILED and not force:
            raise AccountingExportInvalidState("export_failed")

        period = self._load_period(str(batch.billing_period_id))
        actor = actor_from_token(token)
        resource = ResourceContext(
            resource_type="ACCOUNTING_EXPORT",
            tenant_id=actor.tenant_id,
            client_id=None,
            status=period.status.value if period.status else None,
        )
        decision = self.policy_engine.check(
            actor=actor,
            action=Action.ACCOUNTING_EXPORT_CREATE,
            resource=resource,
        )
        if not decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=Action.ACCOUNTING_EXPORT_CREATE,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise PolicyAccessDenied(decision)
        decision_engine = DecisionEngine(self.db)
        actor_id = actor.user_id or actor.client_id or f"tenant-{actor.tenant_id}"
        decision_ctx = DecisionContext(
            tenant_id=actor.tenant_id,
            client_id=actor_id,
            amount=None,
            action=RiskScoreAction.INVOICE,
            metadata={"subject_id": str(batch.id)},
        )
        decision_result = decision_engine.evaluate(decision_ctx)
        if decision_result.outcome != DecisionOutcome.ALLOW:
            reason = "manual_review_required" if decision_result.outcome == DecisionOutcome.MANUAL_REVIEW else "risk_decline"
            raise AccountingExportRiskDeclined(reason)

        self._require_period_finalized(period, request_ctx=request_ctx)

        generated_at = self._stable_generated_at(period, batch)
        batch.generated_at = generated_at

        try:
            export_payload = self._build_payload(batch, generated_at=generated_at)
            checksum = hashlib.sha256(export_payload.payload).hexdigest()
            batch.checksum_sha256 = checksum
            batch.records_count = export_payload.records_count
            batch.state = AccountingExportState.GENERATED
            self.db.flush()

            self._audit_event(
                event_type="ACCOUNTING_EXPORT_GENERATED",
                batch=batch,
                request_ctx=request_ctx,
                extra={
                    "records_count": export_payload.records_count,
                    "checksum_sha256": checksum,
                },
            )
            try:
                graph_context = GraphContext(tenant_id=batch.tenant_id, request_ctx=request_ctx)
                LegalGraphBuilder(self.db, context=graph_context).ensure_accounting_export_graph(batch)
            except Exception as exc:  # noqa: BLE001 - graph should not block exports
                logger.warning(
                    "legal_graph_export_generated_failed",
                    extra={"batch_id": str(batch.id), "error": str(exc)},
                )
                audit_graph_write_failure(
                    self.db,
                    failure=LegalGraphWriteFailure(
                        entity_type="accounting_export_batch",
                        entity_id=str(batch.id),
                        error=str(exc),
                    ),
                    request_ctx=request_ctx,
                )

            object_key = self._build_object_key(batch, checksum)
            storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS)
            storage.put_bytes(object_key, export_payload.payload, content_type=self._content_type(batch.format))

            batch.object_key = object_key
            batch.bucket = storage.bucket
            batch.size_bytes = len(export_payload.payload)
            batch.uploaded_at = datetime.now(timezone.utc)
            batch.state = AccountingExportState.UPLOADED
            batch.error_message = None
            self.db.flush()

            metadata_payload, metadata_checksum, metadata_key = self._build_metadata_payload(
                batch,
                export_checksum=checksum,
                generated_at=generated_at,
            )
            storage.put_bytes(metadata_key, metadata_payload, content_type="application/json")

            self._audit_event(
                event_type="ACCOUNTING_EXPORT_UPLOADED",
                batch=batch,
                request_ctx=request_ctx,
                extra={
                    "object_key": batch.object_key,
                    "bucket": batch.bucket,
                    "size_bytes": batch.size_bytes,
                    "metadata_key": metadata_key,
                    "metadata_checksum": metadata_checksum,
                },
            )
        except Exception as exc:
            batch.state = AccountingExportState.FAILED
            batch.error_message = str(exc)
            self.db.flush()
            self._audit_event(
                event_type="ACCOUNTING_EXPORT_FAILED",
                batch=batch,
                request_ctx=request_ctx,
                extra={"error_message": batch.error_message},
            )
            raise

        return batch

    def download_export(
        self,
        *,
        batch_id: str,
        request_ctx: RequestContext | None,
        token: dict | None = None,
    ) -> bytes:
        batch = self._load_batch(batch_id)
        actor = actor_from_token(token)
        resource = ResourceContext(
            resource_type="ACCOUNTING_EXPORT",
            tenant_id=actor.tenant_id,
            client_id=None,
            status=None,
        )
        decision = self.policy_engine.check(
            actor=actor,
            action=Action.ACCOUNTING_EXPORT_CREATE,
            resource=resource,
        )
        if not decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=Action.ACCOUNTING_EXPORT_CREATE,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise PolicyAccessDenied(decision)
        if not batch.object_key or not batch.bucket:
            raise AccountingExportInvalidState("export_not_uploaded")

        storage = S3Storage(bucket=batch.bucket)
        payload = storage.get_bytes(batch.object_key)
        if payload is None:
            raise AccountingExportNotFound("export_payload_missing")

        batch.downloaded_at = datetime.now(timezone.utc)
        if batch.state != AccountingExportState.CONFIRMED:
            batch.state = AccountingExportState.DOWNLOADED
        self.db.flush()

        self._audit_event(
            event_type="ACCOUNTING_EXPORT_DOWNLOADED",
            batch=batch,
            request_ctx=request_ctx,
            extra={
                "object_key": batch.object_key,
                "bucket": batch.bucket,
            },
        )

        return payload

    def confirm_export(
        self,
        *,
        batch_id: str,
        request_ctx: RequestContext | None,
        erp_system: str,
        erp_import_id: str,
        status: str,
        processed_at: datetime,
        message: str | None = None,
        token: dict | None = None,
    ) -> AccountingExportBatch:
        batch = self._load_batch(batch_id)
        actor = actor_from_token(token)
        resource = ResourceContext(
            resource_type="ACCOUNTING_EXPORT",
            tenant_id=actor.tenant_id,
            client_id=None,
            status=None,
        )
        decision = self.policy_engine.check(
            actor=actor,
            action=Action.ACCOUNTING_EXPORT_CONFIRM,
            resource=resource,
        )
        if not decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=Action.ACCOUNTING_EXPORT_CONFIRM,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise PolicyAccessDenied(decision)
        if status not in {"CONFIRMED", "REJECTED"}:
            raise AccountingExportError("invalid_confirm_status")
        if batch.erp_import_id and batch.erp_import_id != erp_import_id:
            raise AccountingExportInvalidState("erp_import_id_conflict")
        if batch.erp_import_id == erp_import_id and batch.erp_status == status:
            return batch
        if batch.state == AccountingExportState.CONFIRMED and status != "CONFIRMED":
            raise AccountingExportInvalidState("export_already_confirmed")

        batch.erp_system = erp_system
        batch.erp_import_id = erp_import_id
        batch.erp_status = status
        batch.erp_message = message
        batch.erp_processed_at = processed_at

        if status == "CONFIRMED":
            batch.state = AccountingExportState.CONFIRMED
            batch.confirmed_at = datetime.now(timezone.utc)
            batch.error_message = None
            event_type = "ACCOUNTING_EXPORT_CONFIRMED"
        else:
            batch.state = AccountingExportState.FAILED
            batch.error_message = message
            event_type = "ACCOUNTING_EXPORT_REJECTED"

        self.db.flush()

        self._audit_event(
            event_type=event_type,
            batch=batch,
            request_ctx=request_ctx,
            extra={
                "erp_system": erp_system,
                "erp_import_id": erp_import_id,
                "erp_status": status,
                "erp_message": message,
                "erp_processed_at": processed_at,
            },
        )

        if status == "CONFIRMED":
            try:
                graph_context = GraphContext(tenant_id=batch.tenant_id, request_ctx=request_ctx)
                builder = LegalGraphBuilder(self.db, context=graph_context)
                builder.ensure_accounting_export_graph(batch)
                if batch.billing_period_id:
                    export_node = builder.registry.get_or_create_node(
                        tenant_id=batch.tenant_id,
                        node_type=LegalNodeType.ACCOUNTING_EXPORT_BATCH,
                        ref_id=str(batch.id),
                        ref_table="accounting_export_batches",
                    ).node
                    period_node = builder.registry.get_or_create_node(
                        tenant_id=batch.tenant_id,
                        node_type=LegalNodeType.BILLING_PERIOD,
                        ref_id=str(batch.billing_period_id),
                        ref_table="billing_periods",
                    ).node
                    builder.registry.link_edge(
                        tenant_id=batch.tenant_id,
                        src_node_id=export_node.id,
                        dst_node_id=period_node.id,
                        edge_type=LegalEdgeType.CONFIRMS,
                    )
            except Exception as exc:  # noqa: BLE001 - graph should not block exports
                logger.warning(
                    "legal_graph_export_failed",
                    extra={"batch_id": str(batch.id), "error": str(exc)},
                )
                audit_graph_write_failure(
                    self.db,
                    failure=LegalGraphWriteFailure(
                        entity_type="accounting_export_batch",
                        entity_id=str(batch.id),
                        error=str(exc),
                    ),
                    request_ctx=request_ctx,
                )

        return batch

    def deliver_export(
        self,
        *,
        batch_id: str,
        client_id: str,
        request_ctx: RequestContext | None,
    ) -> AccountingExportBatch:
        batch = self._load_batch(batch_id)
        if not batch.object_key or not batch.bucket:
            raise AccountingExportInvalidState("export_not_uploaded")

        profile = get_onboarding_profile(client_id)
        adapter = build_delivery_adapter(profile)

        storage = S3Storage(bucket=batch.bucket)
        payload = storage.get_bytes(batch.object_key)
        if payload is None:
            raise AccountingExportNotFound("export_payload_missing")

        export_checksum = batch.checksum_sha256 or hashlib.sha256(payload).hexdigest()
        generated_at = batch.generated_at or datetime.now(timezone.utc)
        metadata_payload, metadata_checksum, metadata_key = self._build_metadata_payload(
            batch,
            export_checksum=export_checksum,
            generated_at=generated_at,
        )

        adapter_result = adapter.deliver(
            payloads=[
                DeliveryPayload(
                    filename=batch.object_key.split("/")[-1],
                    payload=payload,
                    content_type=self._content_type(batch.format),
                ),
                DeliveryPayload(
                    filename=metadata_key.split("/")[-1],
                    payload=metadata_payload,
                    content_type="application/json",
                ),
            ]
        )

        self._audit_event(
            event_type="ACCOUNTING_EXPORT_DELIVERED",
            batch=batch,
            request_ctx=request_ctx,
            extra={
                "delivery_target": adapter_result.target,
                "delivery_files": adapter_result.files,
                "metadata_checksum": metadata_checksum,
            },
        )

        return batch

    def list_exports(
        self,
        *,
        period_id: str | None = None,
        state: AccountingExportState | None = None,
        export_type: AccountingExportType | None = None,
        export_format: AccountingExportFormat | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AccountingExportBatch], int]:
        query = self.db.query(AccountingExportBatch)
        if period_id:
            query = query.filter(AccountingExportBatch.billing_period_id == period_id)
        if state:
            query = query.filter(AccountingExportBatch.state == state)
        if export_type:
            query = query.filter(AccountingExportBatch.export_type == export_type)
        if export_format:
            query = query.filter(AccountingExportBatch.format == export_format)
        total = query.count()
        items = (
            query.order_by(AccountingExportBatch.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def _load_period(self, period_id: str) -> BillingPeriod:
        period = self.db.query(BillingPeriod).filter(BillingPeriod.id == period_id).one_or_none()
        if period is None:
            raise AccountingExportNotFound("billing_period_not_found")
        return period

    def _load_batch(self, batch_id: str) -> AccountingExportBatch:
        batch = self.db.query(AccountingExportBatch).filter(AccountingExportBatch.id == batch_id).one_or_none()
        if batch is None:
            raise AccountingExportNotFound("export_batch_not_found")
        return batch

    def _require_period_finalized(self, period: BillingPeriod, *, request_ctx: RequestContext | None) -> None:
        if period.status == BillingPeriodStatus.OPEN:
            AuditService(self.db).audit(
                event_type="ACCOUNTING_EXPORT_FORBIDDEN",
                entity_type="billing_period",
                entity_id=str(period.id),
                action="EXPORT_DENIED",
                visibility=AuditVisibility.INTERNAL,
                after={"status": period.status.value},
                request_ctx=request_ctx,
            )
            raise AccountingExportForbidden("period_not_finalized")

    def _resolve_tenant_id(self, request_ctx: RequestContext | None) -> int:
        if request_ctx and request_ctx.tenant_id is not None:
            return int(request_ctx.tenant_id)
        return 0

    def _reset_failed_batch(self, batch: AccountingExportBatch) -> None:
        batch.state = AccountingExportState.CREATED
        batch.error_message = None
        batch.checksum_sha256 = None
        batch.records_count = 0
        batch.object_key = None
        batch.bucket = None
        batch.size_bytes = None
        batch.generated_at = None
        batch.uploaded_at = None
        batch.downloaded_at = None
        batch.confirmed_at = None

    def _build_payload(self, batch: AccountingExportBatch, *, generated_at: datetime) -> AccountingExportPayload:
        if batch.export_type == AccountingExportType.CHARGES:
            entries = self._load_charge_entries(batch)
            include_mapping, entries = self._apply_erp_mapping(batch, entries)
            if batch.format == AccountingExportFormat.CSV:
                payload = serialize_charges_csv(entries, include_mapping=include_mapping)
            elif batch.format == AccountingExportFormat.JSON:
                payload, _ = serialize_sap_json(
                    batch_id=str(batch.id),
                    export_type=batch.export_type.value,
                    generated_at=generated_at,
                    entries=entries,
                    records_count=len(entries),
                )
            else:
                raise AccountingExportError("format_not_supported")
            return AccountingExportPayload(payload=payload, records_count=len(entries))

        if batch.export_type == AccountingExportType.SETTLEMENT:
            entries = self._load_settlement_entries(batch)
            include_mapping, entries = self._apply_erp_mapping(batch, entries)
            if batch.format == AccountingExportFormat.CSV:
                payload = serialize_settlement_csv(entries, include_mapping=include_mapping)
            elif batch.format == AccountingExportFormat.JSON:
                payload, _ = serialize_sap_json(
                    batch_id=str(batch.id),
                    export_type=batch.export_type.value,
                    generated_at=generated_at,
                    entries=entries,
                    records_count=len(entries),
                )
            else:
                raise AccountingExportError("format_not_supported")
            return AccountingExportPayload(payload=payload, records_count=len(entries))

        raise AccountingExportError("export_type_not_supported")

    def _load_charge_entries(self, batch: AccountingExportBatch) -> list[AccountingEntry]:
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.billing_period_id == str(batch.billing_period_id))
            .order_by(Invoice.id.asc())
            .all()
        )
        return map_charges_entries(batch=batch, invoices=invoices)

    def _load_settlement_entries(self, batch: AccountingExportBatch) -> list[AccountingEntry]:
        allocations = (
            self.db.query(InvoiceSettlementAllocation)
            .filter(InvoiceSettlementAllocation.settlement_period_id == str(batch.billing_period_id))
            .order_by(InvoiceSettlementAllocation.applied_at.asc())
            .all()
        )
        invoice_ids = {allocation.invoice_id for allocation in allocations}
        invoices = (
            self.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all() if invoice_ids else []
        )
        invoice_map = {invoice.id: invoice for invoice in invoices}
        period_ids = {str(invoice.billing_period_id) for invoice in invoices if invoice.billing_period_id}
        periods = (
            self.db.query(BillingPeriod).filter(BillingPeriod.id.in_(period_ids)).all()
            if period_ids
            else []
        )
        period_map = {str(period.id): period for period in periods}

        payments = self._load_payment_sources(
            allocations, source_types={SettlementSourceType.PAYMENT}
        )
        credits = self._load_credit_sources(
            allocations, source_types={SettlementSourceType.CREDIT_NOTE, SettlementSourceType.REFUND}
        )

        return map_settlement_entries(
            batch=batch,
            allocations=allocations,
            invoices=invoice_map,
            billing_periods=period_map,
            payments=payments,
            credits=credits,
        )

    def _load_payment_sources(
        self,
        allocations: Iterable[InvoiceSettlementAllocation],
        *,
        source_types: set[SettlementSourceType],
    ) -> dict[str, InvoicePayment]:
        source_ids = {
            allocation.source_id
            for allocation in allocations
            if allocation.source_type in source_types
        }
        if not source_ids:
            return {}
        payments = self.db.query(InvoicePayment).filter(InvoicePayment.id.in_(source_ids)).all()
        return {str(payment.id): payment for payment in payments}

    def _load_credit_sources(
        self,
        allocations: Iterable[InvoiceSettlementAllocation],
        *,
        source_types: set[SettlementSourceType],
    ) -> dict[str, CreditNote]:
        source_ids = {
            allocation.source_id
            for allocation in allocations
            if allocation.source_type in source_types
        }
        if not source_ids:
            return {}
        credits = self.db.query(CreditNote).filter(CreditNote.id.in_(source_ids)).all()
        return {str(credit.id): credit for credit in credits}

    def _stable_generated_at(self, period: BillingPeriod, batch: AccountingExportBatch) -> datetime:
        if period.locked_at:
            return period.locked_at
        if period.finalized_at:
            return period.finalized_at
        if batch.created_at:
            return batch.created_at
        return datetime.now(timezone.utc)

    def _build_object_key(self, batch: AccountingExportBatch, checksum: str) -> str:
        version = self._extract_version(batch.idempotency_key)
        extension = "csv" if batch.format == AccountingExportFormat.CSV else "json"
        return (
            f"accounting/{batch.billing_period_id}/{batch.export_type.value}/"
            f"{batch.format.value}/v{version}/{checksum}.{extension}"
        )

    def _build_metadata_payload(
        self,
        batch: AccountingExportBatch,
        *,
        export_checksum: str,
        generated_at: datetime,
    ) -> tuple[bytes, str, str]:
        object_key = batch.object_key or self._build_object_key(batch, export_checksum)
        metadata_key = f"{object_key}.metadata.json"
        payload = {
            "schema_version": "1.0",
            "batch_id": str(batch.id),
            "period_id": str(batch.billing_period_id),
            "export_type": batch.export_type.value,
            "format": batch.format.value,
            "records_count": batch.records_count,
            "object_key": object_key,
            "object_key_metadata": metadata_key,
            "sha256": export_checksum,
            "generated_at": generated_at,
            "timestamps": {
                "created_at": batch.created_at,
                "generated_at": generated_at,
                "uploaded_at": batch.uploaded_at,
            },
            "minor_units": 2,
        }
        if batch.erp_profile_id:
            payload["erp_profile_id"] = str(batch.erp_profile_id)
        if batch.erp_system_type:
            payload["erp_system_type"] = batch.erp_system_type.value
        if batch.erp_mapping_id:
            payload["erp_mapping_id"] = str(batch.erp_mapping_id)
        if batch.erp_mapping_version:
            payload["erp_mapping_version"] = batch.erp_mapping_version
        metadata_checksum = hashlib.sha256(serialize_metadata_json(payload)).hexdigest()
        payload["sha256_metadata"] = metadata_checksum
        metadata_payload = serialize_metadata_json(payload)
        return metadata_payload, metadata_checksum, metadata_key

    @staticmethod
    def _build_idempotency_key(
        *,
        period_id: str,
        export_type: AccountingExportType,
        export_format: AccountingExportFormat,
        version: int,
        profile_id: str | None,
        mapping_version: int | None,
    ) -> str:
        suffix = f":v{version}"
        if profile_id:
            suffix = f":profile={profile_id}:v{version}"
            if mapping_version is not None:
                suffix = f":profile={profile_id}:mapv={mapping_version}:v{version}"
        return f"{period_id}:{export_type.value}:{export_format.value}{suffix}"

    @staticmethod
    def _extract_version(idempotency_key: str) -> int:
        try:
            version_token = idempotency_key.split(":")[-1]
            if version_token.startswith("v"):
                return int(version_token[1:])
        except (IndexError, ValueError):
            return 1
        return 1

    @staticmethod
    def _content_type(export_format: AccountingExportFormat) -> str:
        return "text/csv" if export_format == AccountingExportFormat.CSV else "application/json"

    def _audit_event(
        self,
        *,
        event_type: str,
        batch: AccountingExportBatch,
        request_ctx: RequestContext | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        AuditService(self.db).audit(
            event_type=event_type,
            entity_type="accounting_export_batch",
            entity_id=str(batch.id),
            action=event_type.replace("ACCOUNTING_EXPORT_", ""),
            visibility=AuditVisibility.INTERNAL,
            after={
                "batch_id": str(batch.id),
                "period_id": str(batch.billing_period_id),
                "export_type": batch.export_type.value,
                "format": batch.format.value,
                "checksum_sha256": batch.checksum_sha256,
                "records_count": batch.records_count,
                "object_key": batch.object_key,
                "bucket": batch.bucket,
                "erp_profile_id": str(batch.erp_profile_id) if batch.erp_profile_id else None,
                "erp_system_type": batch.erp_system_type.value if batch.erp_system_type else None,
                "erp_mapping_id": str(batch.erp_mapping_id) if batch.erp_mapping_id else None,
                "erp_mapping_version": batch.erp_mapping_version,
                **(extra or {}),
            },
            request_ctx=request_ctx,
        )

    def _load_profile(self, profile_id: str) -> ErpExportProfile:
        profile = (
            self.db.query(ErpExportProfile)
            .filter(ErpExportProfile.id == profile_id, ErpExportProfile.enabled.is_(True))
            .one_or_none()
        )
        if not profile:
            raise AccountingExportNotFound("erp_profile_not_found")
        profile.mapping = None
        if profile.mapping_id:
            mapping = ErpMappingService(self.db).load_mapping(str(profile.mapping_id))
            if mapping.status != ErpMappingStatus.ACTIVE:
                raise AccountingExportError("erp_mapping_inactive")
            profile.mapping = mapping
        return profile

    @staticmethod
    def _resolve_export_format(
        export_format: AccountingExportFormat,
        *,
        profile: ErpExportProfile | None,
    ) -> AccountingExportFormat:
        if not profile:
            return export_format
        if profile.format.value != export_format.value:
            raise AccountingExportError("erp_profile_format_mismatch")
        if export_format not in {AccountingExportFormat.CSV, AccountingExportFormat.JSON}:
            raise AccountingExportError("erp_profile_format_not_supported")
        return export_format

    def _apply_erp_mapping(
        self,
        batch: AccountingExportBatch,
        entries: list[AccountingEntry],
    ) -> tuple[bool, list[AccountingEntry]]:
        if not batch.erp_mapping_id:
            return False, entries
        mapping_service = ErpMappingService(self.db)
        try:
            rules = mapping_service.load_rules(str(batch.erp_mapping_id))
        except ErpMappingNotFound:
            raise AccountingExportError("erp_mapping_not_found") from None
        if not rules:
            return False, entries
        return True, mapping_service.apply_mapping(entries, rules)


__all__ = [
    "AccountingExportError",
    "AccountingExportForbidden",
    "AccountingExportInvalidState",
    "AccountingExportNotFound",
    "AccountingExportService",
]

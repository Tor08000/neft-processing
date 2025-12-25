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
from app.models.audit_log import AuditVisibility
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice
from app.models.risk_score import RiskScoreAction
from app.services.accounting_export.serializer import (
    serialize_accounting_export_json,
    serialize_charges_csv,
    serialize_settlement_csv,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
from app.services.policy import Action, PolicyAccessDenied, PolicyEngine, actor_from_token, audit_access_denied
from app.services.policy.resources import ResourceContext
from app.services.s3_storage import S3Storage


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
            client_id=None,
            actor_type="ADMIN",
            action=DecisionAction.ACCOUNTING_EXPORT,
            billing_period_id=str(period.id),
            history={},
            metadata={
                "billing_period_status": period.status.value if period.status else None,
                "actor_roles": actor.roles,
            },
        )
        decision = DecisionEngine(self.db).evaluate(decision_context)
        if decision.outcome != "ALLOW":
            raise AccountingExportForbidden(f"decision_{decision.outcome.lower()}")
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

        idempotency_key = self._build_idempotency_key(
            period_id=period_id,
            export_type=export_type,
            export_format=export_format,
            version=version,
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

            self._audit_event(
                event_type="ACCOUNTING_EXPORT_UPLOADED",
                batch=batch,
                request_ctx=request_ctx,
                extra={
                    "object_key": batch.object_key,
                    "bucket": batch.bucket,
                    "size_bytes": batch.size_bytes,
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
    ) -> bytes:
        batch = self._load_batch(batch_id)
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
        batch.state = AccountingExportState.CONFIRMED
        batch.confirmed_at = datetime.now(timezone.utc)
        self.db.flush()

        self._audit_event(
            event_type="ACCOUNTING_EXPORT_CONFIRMED",
            batch=batch,
            request_ctx=request_ctx,
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
            records = self._load_charge_records(str(batch.billing_period_id))
            if batch.format == AccountingExportFormat.CSV:
                payload = serialize_charges_csv(records)
            elif batch.format == AccountingExportFormat.JSON:
                payload, _ = serialize_accounting_export_json(
                    {
                        "period_id": str(batch.billing_period_id),
                        "export_type": batch.export_type.value,
                        "generated_at": generated_at,
                    },
                    records,
                )
            else:
                raise AccountingExportError("format_not_supported")
            return AccountingExportPayload(payload=payload, records_count=len(records))

        if batch.export_type == AccountingExportType.SETTLEMENT:
            records = self._load_settlement_records(str(batch.billing_period_id))
            if batch.format == AccountingExportFormat.CSV:
                payload = serialize_settlement_csv(records)
            elif batch.format == AccountingExportFormat.JSON:
                payload, _ = serialize_accounting_export_json(
                    {
                        "period_id": str(batch.billing_period_id),
                        "export_type": batch.export_type.value,
                        "generated_at": generated_at,
                    },
                    records,
                )
            else:
                raise AccountingExportError("format_not_supported")
            return AccountingExportPayload(payload=payload, records_count=len(records))

        raise AccountingExportError("export_type_not_supported")

    def _load_charge_records(self, period_id: str) -> list[dict[str, Any]]:
        invoices = self.db.query(Invoice).filter(Invoice.billing_period_id == period_id).all()
        records = [
            {
                "period_id": period_id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.number,
                "client_id": invoice.client_id,
                "issued_at": invoice.issued_at,
                "period_from": invoice.period_from,
                "period_to": invoice.period_to,
                "currency": invoice.currency,
                "total_amount": int(invoice.total_amount),
                "tax_amount": int(invoice.tax_amount),
                "total_with_tax": int(invoice.total_with_tax),
                "status": invoice.status,
                "pdf_hash": invoice.pdf_hash,
                "external_number": invoice.external_number,
            }
            for invoice in invoices
        ]
        return sorted(records, key=lambda record: (record["invoice_id"], record["invoice_number"] or ""))

    def _load_settlement_records(self, period_id: str) -> list[dict[str, Any]]:
        allocations = (
            self.db.query(InvoiceSettlementAllocation)
            .filter(InvoiceSettlementAllocation.settlement_period_id == period_id)
            .all()
        )
        invoice_ids = {allocation.invoice_id for allocation in allocations}
        invoices = (
            self.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all() if invoice_ids else []
        )
        invoice_map = {invoice.id: invoice for invoice in invoices}

        payments = self._load_payment_sources(
            allocations, source_types={SettlementSourceType.PAYMENT}
        )
        credits = self._load_credit_sources(
            allocations, source_types={SettlementSourceType.CREDIT_NOTE, SettlementSourceType.REFUND}
        )

        records = []
        for allocation in allocations:
            invoice = invoice_map.get(allocation.invoice_id)
            provider = None
            external_ref = None
            if allocation.source_type == SettlementSourceType.PAYMENT:
                provider, external_ref = payments.get(allocation.source_id, (None, None))
            else:
                provider, external_ref = credits.get(allocation.source_id, (None, None))

            records.append(
                {
                    "settlement_period_id": str(allocation.settlement_period_id),
                    "invoice_id": allocation.invoice_id,
                    "source_type": allocation.source_type,
                    "source_id": allocation.source_id,
                    "amount": int(allocation.amount),
                    "currency": allocation.currency,
                    "applied_at": allocation.applied_at,
                    "charge_period_id": str(invoice.billing_period_id) if invoice and invoice.billing_period_id else None,
                    "provider": provider,
                    "external_ref": external_ref,
                }
            )

        return sorted(
            records,
            key=lambda record: (
                record["invoice_id"],
                record["source_type"].value if record["source_type"] else "",
                record["source_id"],
                record["applied_at"].isoformat() if record["applied_at"] else "",
            ),
        )

    def _load_payment_sources(
        self,
        allocations: Iterable[InvoiceSettlementAllocation],
        *,
        source_types: set[SettlementSourceType],
    ) -> dict[str, tuple[str | None, str | None]]:
        source_ids = {
            allocation.source_id
            for allocation in allocations
            if allocation.source_type in source_types
        }
        if not source_ids:
            return {}
        payments = self.db.query(InvoicePayment).filter(InvoicePayment.id.in_(source_ids)).all()
        return {str(payment.id): (payment.provider, payment.external_ref) for payment in payments}

    def _load_credit_sources(
        self,
        allocations: Iterable[InvoiceSettlementAllocation],
        *,
        source_types: set[SettlementSourceType],
    ) -> dict[str, tuple[str | None, str | None]]:
        source_ids = {
            allocation.source_id
            for allocation in allocations
            if allocation.source_type in source_types
        }
        if not source_ids:
            return {}
        credits = self.db.query(CreditNote).filter(CreditNote.id.in_(source_ids)).all()
        return {str(credit.id): (credit.provider, credit.external_ref) for credit in credits}

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

    @staticmethod
    def _build_idempotency_key(
        *,
        period_id: str,
        export_type: AccountingExportType,
        export_format: AccountingExportFormat,
        version: int,
    ) -> str:
        return f"{period_id}:{export_type.value}:{export_format.value}:v{version}"

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
                **(extra or {}),
            },
            request_ctx=request_ctx,
        )


__all__ = [
    "AccountingExportError",
    "AccountingExportForbidden",
    "AccountingExportInvalidState",
    "AccountingExportNotFound",
    "AccountingExportService",
]

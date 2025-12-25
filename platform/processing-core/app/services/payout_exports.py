from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO

from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models.billing_period import BillingPeriod
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFile, PayoutExportFormat, PayoutExportState
from app.models.risk_score import RiskScoreAction
from app.services.decision import DecisionContext, DecisionEngine, DecisionOutcome
from app.services.payout_export_xlsx import (
    PayoutXlsxResult,
    generate_payout_registry_xlsx,
)
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
from app.services.policy import Action, PolicyAccessDenied, PolicyEngine, actor_from_token, audit_access_denied
from app.services.policy.resources import ResourceContext
from app.services.s3_storage import S3Storage


class PayoutExportError(Exception):
    """Domain error for payout exports."""


class PayoutExportConflictError(PayoutExportError):
    """Raised when external references conflict."""


@dataclass(frozen=True)
class PayoutExportResult:
    export: PayoutExportFile
    created: bool


def _build_object_key(
    batch: PayoutBatch,
    export_format: PayoutExportFormat,
    *,
    bank_format_code: str | None,
    external_ref: str | None,
    export_id: str,
) -> str:
    date_from = batch.date_from.isoformat()
    date_to = batch.date_to.isoformat()
    if export_format == PayoutExportFormat.XLSX:
        ref = external_ref or f"export-{export_id}"
        return (
            f"payouts/{batch.partner_id}/{date_from}_{date_to}/{batch.id}/"
            f"{bank_format_code}_{ref}.xlsx"
        )
    return f"payouts/{batch.partner_id}/{date_from}_{date_to}/{batch.id}/registry.csv"


def _render_csv(batch: PayoutBatch, generated_at: datetime) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Batch ID", batch.id])
    writer.writerow(["Partner ID", batch.partner_id])
    writer.writerow(["Period from", batch.date_from.isoformat()])
    writer.writerow(["Period to", batch.date_to.isoformat()])
    writer.writerow(["Total amount (net)", str(batch.total_amount)])
    writer.writerow(["Generated at", generated_at.isoformat()])
    writer.writerow([])
    writer.writerow(
        [
            "item_id",
            "azs_id",
            "amount_gross",
            "commission_amount",
            "amount_net",
            "qty",
            "operations_count",
            "partner_bank_account",
            "partner_bik",
            "partner_inn",
        ]
    )
    for item in batch.items or []:
        writer.writerow(
            [
                item.id,
                item.azs_id or "",
                str(item.amount_gross),
                str(item.commission_amount),
                str(item.amount_net),
                str(item.qty),
                str(item.operations_count),
                "",
                "",
                "",
            ]
        )
    return output.getvalue().encode("utf-8")


def _content_type(export_format: PayoutExportFormat) -> str:
    if export_format == PayoutExportFormat.XLSX:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/csv"


def _load_batch(db: Session, batch_id: str) -> PayoutBatch | None:
    return (
        db.query(PayoutBatch)
        .options(selectinload(PayoutBatch.items))
        .filter(PayoutBatch.id == batch_id)
        .one_or_none()
    )


def _find_existing_export(
    db: Session,
    *,
    batch_id: str,
    export_format: PayoutExportFormat,
    bank_format_code: str | None,
    provider: str | None,
    external_ref: str | None,
) -> PayoutExportFile | None:
    query = db.query(PayoutExportFile).filter(
        PayoutExportFile.batch_id == batch_id,
        PayoutExportFile.format == export_format,
        PayoutExportFile.bank_format_code == bank_format_code,
        PayoutExportFile.provider == provider,
    )
    if external_ref is None:
        query = query.filter(PayoutExportFile.external_ref.is_(None))
    else:
        query = query.filter(PayoutExportFile.external_ref == external_ref)
    return query.one_or_none()


def create_payout_export(
    db: Session,
    *,
    batch_id: str,
    export_format: PayoutExportFormat,
    provider: str | None,
    external_ref: str | None,
    bank_format_code: str | None = None,
    token: dict | None = None,
) -> PayoutExportResult:
    if export_format == PayoutExportFormat.XLSX and not bank_format_code:
        raise PayoutExportError("bank_format_required")

    batch = _load_batch(db, batch_id)
    if not batch:
        raise PayoutExportError("batch_not_found")
    if batch.state not in {PayoutBatchState.READY, PayoutBatchState.SENT, PayoutBatchState.SETTLED}:
        raise PayoutExportError("invalid_state")

    period_status = None
    billing_period_id = None
    if batch.meta and isinstance(batch.meta, dict):
        billing_period_id = batch.meta.get("billing_period_id")
    if billing_period_id:
        period = db.query(BillingPeriod).filter(BillingPeriod.id == billing_period_id).one_or_none()
        if period and period.status:
            period_status = period.status.value

    actor = actor_from_token(token)
    resource = ResourceContext(
        resource_type="PAYOUT_BATCH",
        tenant_id=actor.tenant_id or int(batch.tenant_id),
        client_id=None,
        status=period_status,
    )
    decision_context = DecisionContext(
        tenant_id=actor.tenant_id or int(batch.tenant_id),
        client_id=None,
        actor_type="ADMIN",
        action=DecisionAction.PAYOUT_EXPORT,
        billing_period_id=billing_period_id,
        history={},
        metadata={
            "billing_period_status": period_status,
            "actor_roles": actor.roles,
        },
    )
    decision = DecisionEngine(db).evaluate(decision_context)
    if decision.outcome != "ALLOW":
        raise PayoutExportError(f"decision_{decision.outcome.lower()}")
    policy_decision = PolicyEngine().check(actor=actor, action=Action.PAYOUT_EXPORT_CREATE, resource=resource)
    if not policy_decision.allowed:
        audit_access_denied(
            db,
            actor=actor,
            action=Action.PAYOUT_EXPORT_CREATE,
            resource=resource,
            decision=policy_decision,
            token=token,
        )
        raise PolicyAccessDenied(policy_decision)

    decision_engine = DecisionEngine(db)
    actor_id = actor.user_id or actor.client_id or f"tenant-{batch.tenant_id}"
    decision_ctx = DecisionContext(
        tenant_id=actor.tenant_id or int(batch.tenant_id),
        client_id=actor_id,
        amount=float(batch.total_amount or 0),
        action=RiskScoreAction.PAYOUT,
    )
    decision_result = decision_engine.evaluate(decision_ctx)
    if decision_result.outcome != DecisionOutcome.ALLOW:
        reason = "manual_review_required" if decision_result.outcome == DecisionOutcome.MANUAL_REVIEW else "risk_decline"
        raise PayoutExportError(reason)

    if external_ref:
        conflict = (
            db.query(PayoutExportFile)
            .filter(
                PayoutExportFile.provider == provider,
                PayoutExportFile.external_ref == external_ref,
                PayoutExportFile.batch_id != batch_id,
            )
            .one_or_none()
        )
        if conflict:
            raise PayoutExportConflictError("external_ref_conflict")

    existing = _find_existing_export(
        db,
        batch_id=batch_id,
        export_format=export_format,
        bank_format_code=bank_format_code,
        provider=provider,
        external_ref=external_ref,
    )
    if existing and existing.state in {PayoutExportState.GENERATED, PayoutExportState.UPLOADED}:
        return PayoutExportResult(export=existing, created=False)

    export_record = existing
    created = False
    if not export_record:
        export_record = PayoutExportFile(
            batch_id=batch_id,
            format=export_format,
            state=PayoutExportState.DRAFT,
            provider=provider,
            external_ref=external_ref,
            bank_format_code=bank_format_code,
            object_key="",
            bucket=settings.NEFT_S3_BUCKET_PAYOUTS,
        )
        db.add(export_record)
        db.flush()
        created = True
        export_record.object_key = _build_object_key(
            batch,
            export_format,
            bank_format_code=bank_format_code,
            external_ref=external_ref,
            export_id=export_record.id,
        )
        db.flush()

    generated_at = datetime.now(timezone.utc)
    try:
        payload: bytes
        meta: dict | None = None
        if export_format == PayoutExportFormat.CSV:
            payload = _render_csv(batch, generated_at=generated_at)
        elif export_format == PayoutExportFormat.XLSX:
            if not bank_format_code:
                raise PayoutExportError("bank_format_required")
            try:
                xlsx_result: PayoutXlsxResult = generate_payout_registry_xlsx(
                    db,
                    batch_id=batch.id,
                    format_code=bank_format_code,
                    provider=provider,
                    external_ref=external_ref,
                )
            except ValueError as exc:
                raise PayoutExportError(str(exc)) from exc
            payload = xlsx_result.payload
            meta = xlsx_result.meta
        else:
            raise PayoutExportError("format_not_supported")

        payload_hash = hashlib.sha256(payload).hexdigest()
        storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_PAYOUTS)
        storage.put_bytes(
            export_record.object_key,
            payload,
            content_type=_content_type(export_format),
        )
        export_record.state = PayoutExportState.UPLOADED
        export_record.generated_at = generated_at
        export_record.uploaded_at = datetime.now(timezone.utc)
        export_record.sha256 = payload_hash
        export_record.size_bytes = len(payload)
        export_record.error_message = None
        export_record.bucket = storage.bucket
        if meta is not None:
            export_record.meta = meta
        db.flush()
    except Exception as exc:
        export_record.state = PayoutExportState.FAILED
        export_record.error_message = str(exc)
        db.flush()
        db.commit()
        raise

    db.commit()
    db.refresh(export_record)

    return PayoutExportResult(export=export_record, created=created)


def list_payout_exports(
    db: Session,
    *,
    batch_id: str,
) -> list[PayoutExportFile]:
    return (
        db.query(PayoutExportFile)
        .filter(PayoutExportFile.batch_id == batch_id)
        .order_by(PayoutExportFile.generated_at.desc().nullslast(), PayoutExportFile.id.desc())
        .all()
    )


def load_export(db: Session, export_id: str) -> PayoutExportFile | None:
    return (
        db.query(PayoutExportFile)
        .options(selectinload(PayoutExportFile.batch))
        .filter(PayoutExportFile.id == export_id)
        .one_or_none()
    )

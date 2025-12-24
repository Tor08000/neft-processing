from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO

from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFile, PayoutExportFormat, PayoutExportState
from app.services.s3_storage import S3Storage


class PayoutExportError(Exception):
    """Domain error for payout exports."""


class PayoutExportConflictError(PayoutExportError):
    """Raised when external references conflict."""


@dataclass(frozen=True)
class PayoutExportResult:
    export: PayoutExportFile
    created: bool


def _build_object_key(batch: PayoutBatch, export_format: PayoutExportFormat) -> str:
    date_from = batch.date_from.isoformat()
    date_to = batch.date_to.isoformat()
    extension = export_format.value.lower()
    return f"payouts/{batch.partner_id}/{date_from}_{date_to}/{batch.id}/registry.{extension}"


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
    provider: str | None,
    external_ref: str | None,
) -> PayoutExportFile | None:
    query = db.query(PayoutExportFile).filter(
        PayoutExportFile.batch_id == batch_id,
        PayoutExportFile.format == export_format,
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
) -> PayoutExportResult:
    batch = _load_batch(db, batch_id)
    if not batch:
        raise PayoutExportError("batch_not_found")
    if batch.state not in {PayoutBatchState.READY, PayoutBatchState.SENT, PayoutBatchState.SETTLED}:
        raise PayoutExportError("invalid_state")

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
            object_key=_build_object_key(batch, export_format),
            bucket=settings.NEFT_S3_BUCKET_PAYOUTS,
        )
        db.add(export_record)
        db.flush()
        created = True

    generated_at = datetime.now(timezone.utc)
    try:
        if export_format != PayoutExportFormat.CSV:
            raise PayoutExportError("format_not_supported")

        payload = _render_csv(batch, generated_at=generated_at)
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

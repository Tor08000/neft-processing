from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payout_export_file import PayoutExportFormat
from app.services.payout_exports import create_payout_export, PayoutExportResult


def export_payout_batch(
    db: Session,
    *,
    batch_id: str,
    export_format: str,
    provider: str | None = None,
    external_ref: str | None = None,
    token: dict | None = None,
) -> PayoutExportResult:
    format_enum = PayoutExportFormat.CSV if export_format.upper() == "CSV" else PayoutExportFormat.XLSX
    return create_payout_export(
        db,
        batch_id=batch_id,
        export_format=format_enum,
        provider=provider,
        external_ref=external_ref,
        token=token,
    )


__all__ = ["export_payout_batch"]

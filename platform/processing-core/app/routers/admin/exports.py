from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from neft_shared.settings import get_settings

from app.db import get_db
from app.models.case_exports import CaseExport
from app.schemas.admin.case_exports import (
    CaseExportCreateRequest,
    CaseExportDownload,
    CaseExportDownloadResponse,
    CaseExportOut,
)
from app.services.admin_auth import require_admin
from app.services.case_events_service import CaseEventActor
from app.services.case_export_service import create_export
from app.services.export_storage import ExportStorage

router = APIRouter(prefix="/exports", tags=["admin-exports"])
settings = get_settings()


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


def _export_to_schema(export: CaseExport, download: CaseExportDownload | None = None) -> CaseExportOut:
    return CaseExportOut(
        id=str(export.id),
        kind=export.kind,
        case_id=str(export.case_id) if export.case_id else None,
        content_type=export.content_type,
        content_sha256=export.content_sha256,
        size_bytes=export.size_bytes,
        created_at=export.created_at,
        deleted_at=export.deleted_at,
        delete_reason=export.delete_reason,
        download=download,
    )


def _load_export(db: Session, export_id: str) -> CaseExport:
    export = db.query(CaseExport).filter(CaseExport.id == export_id).one_or_none()
    if not export or export.deleted_at is not None:
        raise HTTPException(status_code=404, detail="export_not_found")
    return export


@router.post("", response_model=CaseExportOut, status_code=status.HTTP_201_CREATED)
def create_export_endpoint(
    payload: CaseExportCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> CaseExportOut:
    request_id, trace_id = _request_ids(request)
    actor = CaseEventActor(id=token.get("user_id") or token.get("sub"), email=token.get("email"))
    export = create_export(
        db,
        kind=payload.kind.value,
        case_id=UUID(payload.case_id) if payload.case_id else None,
        payload=payload.payload,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
    )
    storage = ExportStorage()
    url = storage.presign_get(export.object_key, ttl_seconds=settings.S3_SIGNED_URL_TTL_SECONDS)
    db.commit()
    return _export_to_schema(
        export,
        download=CaseExportDownload(url=url, expires_in=settings.S3_SIGNED_URL_TTL_SECONDS),
    )


@router.get("/{export_id}", response_model=CaseExportOut)
def get_export_metadata(
    export_id: str,
    db: Session = Depends(get_db),
) -> CaseExportOut:
    export = _load_export(db, export_id)
    return _export_to_schema(export)


@router.post("/{export_id}/download", response_model=CaseExportDownloadResponse)
def get_export_download(
    export_id: str,
    db: Session = Depends(get_db),
) -> CaseExportDownloadResponse:
    export = _load_export(db, export_id)
    storage = ExportStorage()
    url = storage.presign_get(export.object_key, ttl_seconds=settings.S3_SIGNED_URL_TTL_SECONDS)
    return CaseExportDownloadResponse(
        url=url,
        expires_in=settings.S3_SIGNED_URL_TTL_SECONDS,
        content_sha256=export.content_sha256,
    )


__all__ = ["router"]

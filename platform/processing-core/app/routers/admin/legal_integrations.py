from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.legal_integrations import DocumentEnvelopeStatus
from app.services.legal_integrations.base import EnvelopeStatus
from app.services.legal_integrations.errors import EnvelopeNotFound, ProviderNotConfigured
from app.services.legal_integrations.service import LegalIntegrationsService


router = APIRouter(prefix="/legal", tags=["legal"])


class WebhookPayload(BaseModel):
    envelope_id: str
    status: DocumentEnvelopeStatus
    status_at: datetime | None = None
    error_message: str | None = None
    meta: dict | None = None


@router.post("/webhook/{provider}")
def legal_webhook(
    provider: str,
    payload: WebhookPayload,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    service = LegalIntegrationsService(db)
    status = EnvelopeStatus(
        provider=provider,
        envelope_id=payload.envelope_id,
        status=payload.status,
        status_at=payload.status_at,
        error_message=payload.error_message,
        meta=payload.meta,
    )
    try:
        envelope = service.update_envelope_status(
            provider=provider,
            envelope_id=payload.envelope_id,
            status=status,
            request=request,
            token=token,
        )
    except EnvelopeNotFound:
        raise HTTPException(status_code=404, detail="envelope_not_found")
    except ProviderNotConfigured:
        raise HTTPException(status_code=409, detail="provider_not_configured")
    return {"envelope_id": envelope.envelope_id, "provider": envelope.provider, "status": envelope.status.value}


@router.post("/poll/{provider}")
def poll_legal_provider(
    provider: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    service = LegalIntegrationsService(db)
    try:
        updated = service.poll_provider(provider=provider)
    except ProviderNotConfigured:
        raise HTTPException(status_code=409, detail="provider_not_configured")
    return {"provider": provider, "updated": [envelope.envelope_id for envelope in updated]}

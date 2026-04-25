from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.edo.credentials_store import CredentialsStore
from app.integrations.edo.dtos import EdoInboundRequest
from app.models.edo import EdoAccount
from app.services.edo import EdoService
from neft_shared.settings import get_settings


router = APIRouter(prefix="/integrations/edo/sbis", tags=["edo-webhook"])


@router.post("/webhook")
async def sbis_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    payload_bytes = await request.body()
    signature_header = settings.EDO_WEBHOOK_SIGNATURE_HEADER
    signature = request.headers.get(signature_header)
    if not signature:
        raise HTTPException(status_code=401, detail="missing_signature")
    account_id = request.headers.get("x-edo-account-id")
    if not account_id:
        raise HTTPException(status_code=400, detail="missing_account_id")
    account = db.get(EdoAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="edo_account_not_found")
    store = CredentialsStore()
    secret = store.get_webhook_secret(account.webhook_secret_ref)
    service = EdoService(db)
    if not service.verify_webhook_signature(secret, payload_bytes, signature):
        raise HTTPException(status_code=401, detail="invalid_signature")
    payload = await request.json()
    event_id = payload.get("event_id") or payload.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing_event_id")
    event = EdoInboundRequest(
        provider_event_id=str(event_id),
        headers=dict(request.headers),
        payload=payload,
        received_at=datetime.now(timezone.utc),
    )
    result = service.receive(event)
    return {"handled": result.handled, "updated_documents": result.updated_documents}


__all__ = ["router"]

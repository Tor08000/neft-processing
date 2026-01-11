from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.types import new_uuid_str
from app.models.edo import (
    EdoAccount,
    EdoArtifact,
    EdoCounterpartySubjectType,
    EdoCounterparty,
    EdoDocument,
    EdoDocumentKind,
    EdoDocumentStatus,
    EdoOutbox,
    EdoOutboxStatus,
    EdoProvider,
    EdoSubjectType,
    EdoTransition,
)
from app.schemas.edo import (
    EdoAccountIn,
    EdoAccountOut,
    EdoArtifactOut,
    EdoCounterpartyIn,
    EdoCounterpartyOut,
    EdoDocumentOut,
    EdoDocumentSendIn,
    EdoSendResponse,
    EdoTransitionOut,
)
from app.services.edo import EdoService
from app.services.abac import AbacContext, AbacEngine, AbacResource
from app.services.abac.dependency import get_abac_principal
from app.services.entitlements_service import get_entitlements
from app.security.service_auth import require_scope
from app.integrations.edo.dtos import EdoRevokeRequest, EdoStatusRequest


router = APIRouter(prefix="/edo", tags=["edo-admin"])


def _serialize_document(doc: EdoDocument) -> EdoDocumentOut:
    return EdoDocumentOut(
        id=str(doc.id),
        provider=doc.provider.value,
        account_id=str(doc.account_id),
        subject_type=doc.subject_type.value,
        subject_id=doc.subject_id,
        document_registry_id=str(doc.document_registry_id),
        document_kind=doc.document_kind.value,
        provider_doc_id=doc.provider_doc_id,
        provider_thread_id=doc.provider_thread_id,
        status=doc.status.value,
        counterparty_id=str(doc.counterparty_id),
        send_dedupe_key=doc.send_dedupe_key,
        attempts_send=int(doc.attempts_send or 0),
        attempts_status=int(doc.attempts_status or 0),
        next_retry_at=doc.next_retry_at,
        last_error=doc.last_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/accounts", response_model=EdoAccountOut)
def upsert_account(payload: EdoAccountIn, db: Session = Depends(get_db)) -> EdoAccountOut:
    account = db.query(EdoAccount).get(payload.id) if payload.id else None
    if account is None:
        account = EdoAccount(id=new_uuid_str(), provider=EdoProvider.SBIS, name=payload.name)
        db.add(account)
    account.name = payload.name
    account.org_inn = payload.org_inn
    account.box_id = payload.box_id
    account.credentials_ref = payload.credentials_ref
    account.webhook_secret_ref = payload.webhook_secret_ref
    account.is_active = payload.is_active
    return EdoAccountOut(
        id=str(account.id),
        provider=account.provider.value,
        name=account.name,
        org_inn=account.org_inn,
        box_id=account.box_id,
        credentials_ref=account.credentials_ref,
        webhook_secret_ref=account.webhook_secret_ref,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get("/accounts", response_model=list[EdoAccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[EdoAccountOut]:
    accounts = db.query(EdoAccount).order_by(EdoAccount.created_at.desc()).all()
    return [
        EdoAccountOut(
            id=str(account.id),
            provider=account.provider.value,
            name=account.name,
            org_inn=account.org_inn,
            box_id=account.box_id,
            credentials_ref=account.credentials_ref,
            webhook_secret_ref=account.webhook_secret_ref,
            is_active=account.is_active,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
        for account in accounts
    ]


@router.post("/counterparties", response_model=EdoCounterpartyOut)
def upsert_counterparty(payload: EdoCounterpartyIn, db: Session = Depends(get_db)) -> EdoCounterpartyOut:
    counterparty = db.query(EdoCounterparty).get(payload.id) if payload.id else None
    if counterparty is None:
        counterparty = EdoCounterparty(
            id=new_uuid_str(),
            provider=EdoProvider.SBIS,
            subject_type=EdoCounterpartySubjectType(payload.subject_type),
            subject_id=payload.subject_id,
            provider_counterparty_id=payload.provider_counterparty_id,
        )
        db.add(counterparty)
    counterparty.subject_type = EdoCounterpartySubjectType(payload.subject_type)
    counterparty.subject_id = payload.subject_id
    counterparty.provider_counterparty_id = payload.provider_counterparty_id
    counterparty.provider_box_id = payload.provider_box_id
    counterparty.display_name = payload.display_name
    counterparty.meta = payload.meta
    return EdoCounterpartyOut(
        id=str(counterparty.id),
        provider=counterparty.provider.value,
        subject_type=counterparty.subject_type.value,
        subject_id=counterparty.subject_id,
        provider_counterparty_id=counterparty.provider_counterparty_id,
        provider_box_id=counterparty.provider_box_id,
        display_name=counterparty.display_name,
        meta=counterparty.meta,
        created_at=counterparty.created_at,
        updated_at=counterparty.updated_at,
    )


@router.get("/counterparties", response_model=list[EdoCounterpartyOut])
def list_counterparties(
    subject_type: str | None = Query(None),
    subject_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EdoCounterpartyOut]:
    query = db.query(EdoCounterparty)
    if subject_type:
        query = query.filter(EdoCounterparty.subject_type == EdoCounterpartySubjectType(subject_type))
    if subject_id:
        query = query.filter(EdoCounterparty.subject_id == subject_id)
    records = query.order_by(EdoCounterparty.created_at.desc()).all()
    return [
        EdoCounterpartyOut(
            id=str(item.id),
            provider=item.provider.value,
            subject_type=item.subject_type.value,
            subject_id=item.subject_id,
            provider_counterparty_id=item.provider_counterparty_id,
            provider_box_id=item.provider_box_id,
            display_name=item.display_name,
            meta=item.meta,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in records
    ]


@router.post("/documents/send", response_model=EdoSendResponse)
def send_document(
    payload: EdoDocumentSendIn,
    request: Request,
    _scope=Depends(require_scope("edo:send")),
    db: Session = Depends(get_db),
) -> EdoSendResponse:
    principal = get_abac_principal(request, db)
    entitlements_payload = {}
    if payload.subject_type == EdoSubjectType.CLIENT.value:
        entitlements = get_entitlements(db, client_id=payload.subject_id)
        entitlements_payload = {
            "plan": entitlements.plan_code,
            "modules": entitlements.modules,
            "limits": entitlements.limits,
        }
    decision = AbacEngine(db).evaluate(
        principal=principal,
        action="edo:send",
        resource=AbacResource(
            "EDO_DOCUMENT",
            {
                "subject_type": payload.subject_type,
                "subject_id": payload.subject_id,
                "document_kind": payload.document_kind,
                "account_id": payload.account_id,
            },
        ),
        entitlements=entitlements_payload,
        context=AbacContext(
            ip=request.client.host if request.client else None,
            region=request.headers.get("x-region"),
            timestamp=datetime.now(timezone.utc),
        ),
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "abac_deny",
                "reason_code": decision.reason_code,
                "matched_policies": decision.matched_policies,
                "explain": decision.explain,
            },
        )
    existing = db.query(EdoDocument).filter(EdoDocument.send_dedupe_key == payload.dedupe_key).one_or_none()
    if existing:
        return EdoSendResponse(
            document=_serialize_document(existing),
            provider_doc_id=existing.provider_doc_id,
            status=existing.status.value,
        )
    edo_document = EdoDocument(
        id=new_uuid_str(),
        provider=EdoProvider.SBIS,
        account_id=payload.account_id,
        subject_type=EdoSubjectType(payload.subject_type),
        subject_id=payload.subject_id,
        document_registry_id=payload.document_registry_id,
        document_kind=EdoDocumentKind(payload.document_kind),
        status=EdoDocumentStatus.DRAFT,
        counterparty_id=payload.counterparty_id,
        send_dedupe_key=payload.dedupe_key,
    )
    db.add(edo_document)
    service = EdoService(db)
    outbox = service.enqueue_send(
        edo_document=edo_document,
        dedupe_key=payload.dedupe_key,
        payload={
            "edo_document_id": str(edo_document.id),
            "account_id": payload.account_id,
            "document_registry_id": payload.document_registry_id,
            "counterparty_id": payload.counterparty_id,
            "doc_type": payload.document_kind,
            "meta": payload.meta,
        },
    )
    if outbox.status in {EdoOutboxStatus.PENDING, EdoOutboxStatus.FAILED}:
        service.dispatch_outbox_item(outbox)
    return EdoSendResponse(
        document=_serialize_document(edo_document),
        provider_doc_id=edo_document.provider_doc_id,
        status=edo_document.status.value,
    )


@router.get("/documents/{document_id}", response_model=EdoDocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> EdoDocumentOut:
    doc = db.query(EdoDocument).get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    return _serialize_document(doc)


@router.get("/documents", response_model=list[EdoDocumentOut])
def list_documents(
    status: str | None = Query(None),
    subject_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EdoDocumentOut]:
    query = db.query(EdoDocument)
    if status:
        query = query.filter(EdoDocument.status == EdoDocumentStatus(status))
    if subject_id:
        query = query.filter(EdoDocument.subject_id == subject_id)
    records = query.order_by(EdoDocument.created_at.desc()).all()
    return [_serialize_document(doc) for doc in records]


@router.post("/documents/{document_id}/refresh-status", response_model=EdoDocumentOut)
def refresh_status(document_id: str, db: Session = Depends(get_db)) -> EdoDocumentOut:
    doc = db.query(EdoDocument).get(document_id)
    if not doc or not doc.provider_doc_id:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    service = EdoService(db)
    service.refresh_status(EdoStatusRequest(provider_doc_id=doc.provider_doc_id, account_id=str(doc.account_id)))
    return _serialize_document(doc)


@router.post("/documents/{document_id}/revoke", response_model=EdoDocumentOut)
def revoke_document(document_id: str, reason: str | None = None, db: Session = Depends(get_db)) -> EdoDocumentOut:
    doc = db.query(EdoDocument).get(document_id)
    if not doc or not doc.provider_doc_id:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    service = EdoService(db)
    service.revoke(EdoRevokeRequest(provider_doc_id=doc.provider_doc_id, account_id=str(doc.account_id), reason=reason))
    return _serialize_document(doc)


@router.post("/documents/{document_id}/replay-send", response_model=EdoDocumentOut)
def replay_send(document_id: str, db: Session = Depends(get_db)) -> EdoDocumentOut:
    doc = db.query(EdoDocument).get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    outbox = EdoOutbox(
        id=new_uuid_str(),
        event_type="EDO_SEND_REQUESTED",
        payload={
            "edo_document_id": str(doc.id),
            "account_id": str(doc.account_id),
            "document_registry_id": str(doc.document_registry_id),
            "counterparty_id": str(doc.counterparty_id),
            "doc_type": doc.document_kind.value,
            "meta": {},
        },
        dedupe_key=f"replay:{doc.send_dedupe_key}:{datetime.now(timezone.utc).isoformat()}",
        status=EdoOutboxStatus.PENDING,
    )
    db.add(outbox)
    service = EdoService(db)
    service.dispatch_outbox_item(outbox)
    return _serialize_document(doc)


@router.get("/documents/{document_id}/transitions", response_model=list[EdoTransitionOut])
def list_transitions(document_id: str, db: Session = Depends(get_db)) -> list[EdoTransitionOut]:
    records = (
        db.query(EdoTransition)
        .filter(EdoTransition.edo_document_id == document_id)
        .order_by(EdoTransition.created_at.asc())
        .all()
    )
    return [
        EdoTransitionOut(
            id=str(item.id),
            edo_document_id=str(item.edo_document_id),
            from_status=item.from_status.value if item.from_status else None,
            to_status=item.to_status.value,
            reason_code=item.reason_code,
            payload=item.payload,
            actor_type=item.actor_type.value,
            actor_id=item.actor_id,
            created_at=item.created_at,
        )
        for item in records
    ]


@router.get("/documents/{document_id}/artifacts", response_model=list[EdoArtifactOut])
def list_artifacts(document_id: str, db: Session = Depends(get_db)) -> list[EdoArtifactOut]:
    records = (
        db.query(EdoArtifact)
        .filter(EdoArtifact.edo_document_id == document_id)
        .order_by(EdoArtifact.created_at.desc())
        .all()
    )
    return [
        EdoArtifactOut(
            id=str(item.id),
            edo_document_id=str(item.edo_document_id),
            artifact_type=item.artifact_type.value,
            document_registry_id=str(item.document_registry_id),
            content_hash=item.content_hash,
            provider_ref=item.provider_ref,
            created_at=item.created_at,
        )
        for item in records
    ]


__all__ = ["router"]

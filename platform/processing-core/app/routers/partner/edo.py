from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.edo import EdoArtifact, EdoDocument, EdoSubjectType, EdoTransition
from app.schemas.edo import EdoArtifactOut, EdoDocumentOut, EdoTransitionOut
from app.routers.admin.edo import _serialize_document


router = APIRouter(prefix="/partner/api/v1/edo", tags=["partner-edo"])


@router.get("/documents", response_model=list[EdoDocumentOut])
def list_documents(token: dict = Depends(partner_portal_user), db: Session = Depends(get_db)) -> list[EdoDocumentOut]:
    partner_id = token.get("partner_id")
    if not partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    records = (
        db.query(EdoDocument)
        .filter(EdoDocument.subject_type == EdoSubjectType.PARTNER)
        .filter(EdoDocument.subject_id == str(partner_id))
        .order_by(EdoDocument.created_at.desc())
        .all()
    )
    return [_serialize_document(doc) for doc in records]


@router.get("/documents/{document_id}", response_model=EdoDocumentOut)
def get_document(
    document_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> EdoDocumentOut:
    partner_id = token.get("partner_id")
    doc = db.get(EdoDocument, document_id)
    if not doc or doc.subject_id != str(partner_id):
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    return _serialize_document(doc)


@router.get("/documents/{document_id}/artifacts", response_model=list[EdoArtifactOut])
def list_artifacts(
    document_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> list[EdoArtifactOut]:
    partner_id = token.get("partner_id")
    doc = db.get(EdoDocument, document_id)
    if not doc or doc.subject_id != str(partner_id):
        raise HTTPException(status_code=404, detail="edo_document_not_found")
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


@router.get("/documents/{document_id}/transitions", response_model=list[EdoTransitionOut])
def list_transitions(
    document_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> list[EdoTransitionOut]:
    partner_id = token.get("partner_id")
    doc = db.get(EdoDocument, document_id)
    if not doc or doc.subject_id != str(partner_id):
        raise HTTPException(status_code=404, detail="edo_document_not_found")
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


@router.post("/documents/{document_id}/ack")
def acknowledge_document(
    document_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> dict:
    partner_id = token.get("partner_id")
    doc = db.get(EdoDocument, document_id)
    if not doc or doc.subject_id != str(partner_id):
        raise HTTPException(status_code=404, detail="edo_document_not_found")
    return {"acknowledged": True, "document_id": document_id}


__all__ = ["router"]

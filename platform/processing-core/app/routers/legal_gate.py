from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.legal_document import LegalDocumentStatus
from app.models.legal_gate import LegalSubjectType
from app.schemas.legal_gate import LegalAcceptRequest, LegalAcceptResponse, LegalDocumentOut, LegalRequiredResponse
from app.services.legal_gate import accept_documents, get_missing_documents, get_required_documents

router = APIRouter(prefix="/legal", tags=["legal-gate"])


def _parse_subject(subject_type: str, subject_id: str) -> tuple[LegalSubjectType, str]:
    try:
        parsed = LegalSubjectType(subject_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_subject_type") from exc
    return parsed, subject_id


def _documents_out(documents: list) -> list[LegalDocumentOut]:
    return [
        LegalDocumentOut(
            id=str(doc.id),
            code=doc.code,
            version=doc.version,
            status=doc.status.value if isinstance(doc.status, LegalDocumentStatus) else str(doc.status),
            effective_from=doc.effective_from,
            title=doc.title,
        )
        for doc in documents
    ]


@router.get("/required", response_model=LegalRequiredResponse)
def list_required_documents(
    subject_type: str = Query(..., alias="subject_type"),
    subject_id: str = Query(..., alias="subject_id"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_user),
) -> LegalRequiredResponse:
    parsed_type, parsed_id = _parse_subject(subject_type, subject_id)
    missing = get_missing_documents(db, subject_type=parsed_type, subject_id=parsed_id)
    return LegalRequiredResponse(required=_documents_out(missing))


@router.post("/accept", response_model=LegalAcceptResponse)
def accept_required_documents(
    payload: LegalAcceptRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_user),
) -> LegalAcceptResponse:
    parsed_type, parsed_id = _parse_subject(payload.subject_type, payload.subject_id)
    accepted = accept_documents(
        db,
        subject_type=parsed_type,
        subject_id=parsed_id,
        document_ids=payload.document_ids,
        accept_all=payload.accept_all,
    )
    return LegalAcceptResponse(accepted=accepted)


@router.get("/protected")
def protected_action(
    subject_type: str = Query(..., alias="subject_type"),
    subject_id: str = Query(..., alias="subject_id"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin_user),
) -> dict:
    parsed_type, parsed_id = _parse_subject(subject_type, subject_id)
    missing = get_missing_documents(db, subject_type=parsed_type, subject_id=parsed_id)
    if missing:
        raise HTTPException(
            status_code=428,
            detail={
                "error": "LEGAL_REQUIRED",
                "required": _documents_out(missing),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    return {"ok": True}

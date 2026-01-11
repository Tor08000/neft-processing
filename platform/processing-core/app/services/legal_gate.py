from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.legal_gate import (
    LegalAcceptance,
    LegalDocument,
    LegalDocumentStatus,
    LegalSubjectType,
)


@dataclass(frozen=True)
class RequiredResult:
    required: list[LegalDocument]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_required_documents(db: Session, *, as_of: datetime | None = None) -> RequiredResult:
    snapshot = as_of or _now()
    rows = (
        db.query(LegalDocument)
        .filter(LegalDocument.status == LegalDocumentStatus.PUBLISHED)
        .filter(LegalDocument.effective_from <= snapshot)
        .order_by(LegalDocument.code.asc(), desc(LegalDocument.effective_from), desc(LegalDocument.version))
        .all()
    )
    by_code: dict[str, LegalDocument] = {}
    for doc in rows:
        if doc.code not in by_code:
            by_code[doc.code] = doc
    return RequiredResult(required=list(by_code.values()))


def get_missing_documents(
    db: Session,
    *,
    subject_type: LegalSubjectType,
    subject_id: str,
    as_of: datetime | None = None,
) -> list[LegalDocument]:
    required = get_required_documents(db, as_of=as_of).required
    if not required:
        return []
    required_ids = [doc.id for doc in required]
    accepted = (
        db.query(LegalAcceptance.document_id)
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == subject_id)
        .filter(LegalAcceptance.document_id.in_(required_ids))
        .all()
    )
    accepted_ids = {row[0] for row in accepted}
    return [doc for doc in required if doc.id not in accepted_ids]


def accept_documents(
    db: Session,
    *,
    subject_type: LegalSubjectType,
    subject_id: str,
    document_ids: list[str] | None = None,
    accept_all: bool = False,
) -> list[str]:
    if accept_all:
        document_ids = [doc.id for doc in get_required_documents(db).required]
    if not document_ids:
        return []

    existing = (
        db.query(LegalAcceptance.document_id)
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == subject_id)
        .filter(LegalAcceptance.document_id.in_(document_ids))
        .all()
    )
    existing_ids = {row[0] for row in existing}
    new_ids = [doc_id for doc_id in document_ids if doc_id not in existing_ids]
    for doc_id in new_ids:
        db.add(
            LegalAcceptance(
                subject_type=subject_type,
                subject_id=subject_id,
                document_id=doc_id,
                accepted_at=_now(),
            )
        )
    db.commit()
    return new_ids


def ensure_default_legal_documents(db: Session) -> None:
    try:
        existing = db.query(LegalDocument).filter(LegalDocument.status == LegalDocumentStatus.PUBLISHED).count()
    except SQLAlchemyError:
        db.rollback()
        return
    if existing:
        return
    db.add_all(
        [
            LegalDocument(
                code="LEGAL_TERMS",
                title="Legal terms",
                version=1,
                status=LegalDocumentStatus.PUBLISHED,
                effective_from=_now(),
            ),
            LegalDocument(
                code="DATA_PROCESSING",
                title="Data processing addendum",
                version=1,
                status=LegalDocumentStatus.PUBLISHED,
                effective_from=_now(),
            ),
        ]
    )
    db.commit()


__all__ = [
    "get_required_documents",
    "get_missing_documents",
    "accept_documents",
    "ensure_default_legal_documents",
    "RequiredResult",
]

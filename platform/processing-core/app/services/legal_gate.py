from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.legal_acceptance import LegalAcceptance, LegalSubjectType
from app.models.legal_document import LegalDocument, LegalDocumentContentType, LegalDocumentStatus
from app.services.legal import LegalService, LegalSubject


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
    accepted = (
        db.query(
            LegalAcceptance.document_code,
            LegalAcceptance.document_version,
            LegalAcceptance.document_locale,
        )
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == subject_id)
        .filter(LegalAcceptance.document_code.in_([doc.code for doc in required]))
        .all()
    )
    accepted_keys = {(row[0], row[1], row[2]) for row in accepted}
    return [doc for doc in required if (doc.code, doc.version, doc.locale) not in accepted_keys]


def accept_documents(
    db: Session,
    *,
    subject_type: LegalSubjectType,
    subject_id: str,
    document_ids: list[str] | None = None,
    accept_all: bool = False,
) -> list[str]:
    if accept_all:
        documents = get_required_documents(db).required
    else:
        if not document_ids:
            return []
        documents = db.query(LegalDocument).filter(LegalDocument.id.in_(document_ids)).all()

    if not documents:
        return []

    existing = (
        db.query(
            LegalAcceptance.document_code,
            LegalAcceptance.document_version,
            LegalAcceptance.document_locale,
        )
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == subject_id)
        .filter(LegalAcceptance.document_code.in_([doc.code for doc in documents]))
        .all()
    )
    existing_keys = {(row[0], row[1], row[2]) for row in existing}
    now = _now()
    service = LegalService(db)
    subject = LegalSubject(subject_type=subject_type, subject_id=subject_id)
    accepted_ids: list[str] = []
    for doc in documents:
        key = (doc.code, doc.version, doc.locale)
        if key in existing_keys:
            continue
        acceptance_hash = service.compute_acceptance_hash(
            subject=subject,
            document=doc,
            accepted_at=now,
            ip=None,
            user_agent=None,
        )
        db.add(
            LegalAcceptance(
                subject_type=subject_type,
                subject_id=subject_id,
                document_code=doc.code,
                document_version=str(doc.version),
                document_locale=doc.locale,
                accepted_at=now,
                acceptance_hash=acceptance_hash,
                ip=None,
                user_agent=None,
                signature=None,
                meta=None,
            )
        )
        accepted_ids.append(str(doc.id))
    db.commit()
    return accepted_ids


def ensure_default_legal_documents(db: Session) -> None:
    try:
        existing = db.query(LegalDocument).filter(LegalDocument.status == LegalDocumentStatus.PUBLISHED).count()
    except SQLAlchemyError:
        db.rollback()
        return
    if existing:
        return
    service = LegalService(db)
    db.add_all(
        [
            LegalDocument(
                code="LEGAL_TERMS",
                version="1",
                title="Legal terms",
                locale="ru",
                effective_from=_now(),
                status=LegalDocumentStatus.PUBLISHED,
                content_type=LegalDocumentContentType.MARKDOWN,
                content="TBD",
                content_hash=service.compute_content_hash("TBD"),
                published_at=_now(),
            ),
            LegalDocument(
                code="DATA_PROCESSING",
                version="1",
                title="Data processing addendum",
                locale="ru",
                effective_from=_now(),
                status=LegalDocumentStatus.PUBLISHED,
                content_type=LegalDocumentContentType.MARKDOWN,
                content="TBD",
                content_hash=service.compute_content_hash("TBD"),
                published_at=_now(),
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

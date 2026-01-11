from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, Request, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from neft_shared.settings import get_settings

from app.models.audit_log import AuditVisibility
from app.models.legal_acceptance import LegalAcceptance, LegalSubjectType
from app.models.legal_document import LegalDocument, LegalDocumentContentType, LegalDocumentStatus
from app.services.audit_service import AuditService, RequestContext, request_context_from_request


settings = get_settings()

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class LegalSubject:
    subject_type: LegalSubjectType
    subject_id: str


class LegalService:
    def __init__(self, db: Session):
        self.db = db

    def _canonical_content(self, content: str) -> str:
        return content.strip().replace("\r\n", "\n")

    def compute_content_hash(self, content: str) -> str:
        normalized = self._canonical_content(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def compute_acceptance_hash(
        self,
        *,
        subject: LegalSubject,
        document: LegalDocument,
        accepted_at: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> str:
        payload = {
            "subject_type": subject.subject_type.value,
            "subject_id": subject.subject_id,
            "document_code": document.code,
            "document_version": document.version,
            "document_locale": document.locale,
            "effective_from": document.effective_from,
            "content_hash": document.content_hash,
            "accepted_at": accepted_at,
            "ip": ip,
            "user_agent": user_agent,
        }
        normalized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def required_documents(
        self,
        *,
        subject: LegalSubject,
        required_codes: Iterable[str],
        now: datetime | None = None,
    ) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        codes = [code for code in required_codes if code]
        if not codes:
            return []

        documents = (
            self.db.query(LegalDocument)
            .filter(
                LegalDocument.code.in_(codes),
                LegalDocument.status == LegalDocumentStatus.PUBLISHED,
                LegalDocument.effective_from <= now,
            )
            .order_by(
                LegalDocument.code.asc(),
                LegalDocument.locale.asc(),
                LegalDocument.effective_from.desc(),
                LegalDocument.version.desc(),
            )
            .all()
        )

        latest: dict[tuple[str, str], LegalDocument] = {}
        for doc in documents:
            key = (doc.code, doc.locale)
            if key not in latest:
                latest[key] = doc

        if not latest:
            return []

        acceptances = (
            self.db.query(LegalAcceptance)
            .filter(
                LegalAcceptance.subject_type == subject.subject_type,
                LegalAcceptance.subject_id == subject.subject_id,
                LegalAcceptance.document_code.in_([doc.code for doc in latest.values()]),
            )
            .all()
        )
        acceptance_map = {
            (item.document_code, item.document_version, item.document_locale): item for item in acceptances
        }

        required = []
        for doc in latest.values():
            acceptance = acceptance_map.get((doc.code, doc.version, doc.locale))
            required.append(
                {
                    "code": doc.code,
                    "title": doc.title,
                    "locale": doc.locale,
                    "required_version": doc.version,
                    "published_at": doc.published_at,
                    "effective_from": doc.effective_from,
                    "content_hash": doc.content_hash,
                    "accepted": acceptance is not None,
                    "accepted_at": acceptance.accepted_at if acceptance else None,
                }
            )

        required.sort(key=lambda item: (item["code"], item["locale"]))
        return required

    def resolve_document(
        self,
        *,
        code: str,
        version: str | None = None,
        locale: str | None = None,
    ) -> LegalDocument:
        query = self.db.query(LegalDocument).filter(LegalDocument.code == code)
        if version:
            query = query.filter(LegalDocument.version == version)
        if locale:
            query = query.filter(LegalDocument.locale == locale)
        query = query.filter(LegalDocument.status == LegalDocumentStatus.PUBLISHED)
        if not version:
            query = query.filter(LegalDocument.effective_from <= datetime.now(timezone.utc))
        query = query.order_by(
            LegalDocument.effective_from.desc(),
            LegalDocument.version.desc(),
        )
        document = query.first()
        if not document:
            raise HTTPException(status_code=404, detail="legal_document_not_found")
        return document

    def create_document(
        self,
        *,
        payload: dict,
        actor_id: str | None,
        request_ctx: RequestContext | None,
    ) -> LegalDocument:
        content_hash = self.compute_content_hash(payload["content"])
        document = LegalDocument(
            code=payload["code"],
            version=str(payload["version"]),
            title=payload["title"],
            locale=payload.get("locale") or "ru",
            effective_from=payload["effective_from"],
            status=LegalDocumentStatus.DRAFT,
            content_type=LegalDocumentContentType(payload["content_type"]),
            content=payload["content"],
            content_hash=content_hash,
            created_by=actor_id,
        )
        self.db.add(document)
        self.db.flush()
        AuditService(self.db).audit(
            event_type="LEGAL_DOC_CREATED",
            entity_type="legal_document",
            entity_id=str(document.id),
            action="create",
            visibility=AuditVisibility.INTERNAL,
            after=_document_audit_payload(document),
            request_ctx=request_ctx,
        )
        return document

    def update_document(
        self,
        *,
        document: LegalDocument,
        payload: dict,
        request_ctx: RequestContext | None,
    ) -> LegalDocument:
        before = _document_audit_payload(document)
        document.title = payload["title"]
        document.locale = payload["locale"]
        document.effective_from = payload["effective_from"]
        document.content_type = LegalDocumentContentType(payload["content_type"])
        document.content = payload["content"]
        document.content_hash = self.compute_content_hash(payload["content"])
        self.db.add(document)
        self.db.flush()
        AuditService(self.db).audit(
            event_type="LEGAL_DOC_UPDATED",
            entity_type="legal_document",
            entity_id=str(document.id),
            action="update",
            visibility=AuditVisibility.INTERNAL,
            before=before,
            after=_document_audit_payload(document),
            request_ctx=request_ctx,
        )
        return document

    def publish_document(
        self,
        *,
        document: LegalDocument,
        request_ctx: RequestContext | None,
    ) -> LegalDocument:
        if document.status != LegalDocumentStatus.DRAFT:
            raise HTTPException(status_code=400, detail="legal_document_not_draft")
        before = _document_audit_payload(document)
        document.content_hash = self.compute_content_hash(document.content)
        document.status = LegalDocumentStatus.PUBLISHED
        document.published_at = datetime.now(timezone.utc)
        self.db.add(document)

        self.db.query(LegalDocument).filter(
            LegalDocument.code == document.code,
            LegalDocument.locale == document.locale,
            LegalDocument.status == LegalDocumentStatus.PUBLISHED,
            LegalDocument.id != document.id,
        ).update({"status": LegalDocumentStatus.ARCHIVED})
        self.db.flush()

        AuditService(self.db).audit(
            event_type="LEGAL_DOC_PUBLISHED",
            entity_type="legal_document",
            entity_id=str(document.id),
            action="publish",
            visibility=AuditVisibility.INTERNAL,
            before=before,
            after=_document_audit_payload(document),
            request_ctx=request_ctx,
        )
        return document

    def accept_document(
        self,
        *,
        subject: LegalSubject,
        document: LegalDocument,
        ip: str | None,
        user_agent: str | None,
        signature: dict | None,
        meta: dict | None,
        request_ctx: RequestContext | None,
    ) -> LegalAcceptance:
        accepted_at = datetime.now(timezone.utc)
        acceptance_hash = self.compute_acceptance_hash(
            subject=subject,
            document=document,
            accepted_at=accepted_at,
            ip=ip,
            user_agent=user_agent,
        )
        acceptance = LegalAcceptance(
            subject_type=subject.subject_type,
            subject_id=subject.subject_id,
            document_code=document.code,
            document_version=document.version,
            document_locale=document.locale,
            accepted_at=accepted_at,
            ip=ip,
            user_agent=user_agent,
            acceptance_hash=acceptance_hash,
            signature=signature,
            meta=meta,
        )
        self.db.add(acceptance)
        self.db.flush()
        AuditService(self.db).audit(
            event_type="LEGAL_ACCEPTED",
            entity_type="legal_acceptance",
            entity_id=str(acceptance.id),
            action="accept",
            visibility=AuditVisibility.INTERNAL,
            after={
                "subject_type": subject.subject_type.value,
                "subject_id": subject.subject_id,
                "document_code": document.code,
                "document_version": document.version,
                "document_locale": document.locale,
                "content_hash": document.content_hash,
                "acceptance_hash": acceptance_hash,
            },
            request_ctx=request_ctx,
        )
        return acceptance



def _document_audit_payload(document: LegalDocument) -> dict:
    return {
        "code": document.code,
        "version": document.version,
        "title": document.title,
        "locale": document.locale,
        "effective_from": document.effective_from,
        "status": document.status.value,
        "content_type": document.content_type.value,
        "content_hash": document.content_hash,
        "published_at": document.published_at,
    }


def legal_gate_required_codes() -> list[str]:
    raw = getattr(settings, "LEGAL_REQUIRED_DOCS", "") or ""
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    return parts


def legal_gate_exempt_roles() -> set[str]:
    raw = getattr(settings, "LEGAL_GATE_EXEMPT_ROLES", "") or ""
    return {item.strip().upper() for item in raw.split(",") if item.strip()}


def legal_gate_enabled() -> bool:
    return bool(getattr(settings, "LEGAL_GATE_ENABLED", False))


def client_ip_from_request(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def enforce_legal_gate(
    *,
    db: Session,
    request: Request,
    subject: LegalSubject,
    actor_roles: Iterable[str] | None = None,
) -> None:
    if not legal_gate_enabled():
        return
    if request.method in SAFE_METHODS:
        return
    required_codes = legal_gate_required_codes()
    if not required_codes:
        return
    roles = {role.upper() for role in (actor_roles or [])}
    if roles.intersection(legal_gate_exempt_roles()):
        return

    service = LegalService(db)
    required = service.required_documents(subject=subject, required_codes=required_codes)
    blocked = any(not item["accepted"] for item in required)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={
                "error": {
                    "code": "LEGAL_REQUIRED",
                    "message": "Legal documents must be accepted before performing this action.",
                    "details": {"required": required},
                }
            },
        )


def subject_from_request(
    *,
    subject_type: LegalSubjectType,
    subject_id: str,
) -> LegalSubject:
    return LegalSubject(subject_type=subject_type, subject_id=subject_id)


__all__ = [
    "LegalService",
    "LegalSubject",
    "client_ip_from_request",
    "enforce_legal_gate",
    "legal_gate_enabled",
    "legal_gate_exempt_roles",
    "legal_gate_required_codes",
    "subject_from_request",
]

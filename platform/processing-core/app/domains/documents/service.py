from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import OperationalError

from datetime import date, datetime, timezone

from app.domains.documents.models import (
    Document,
    DocumentDirection,
    DocumentFile,
    DocumentSenderType,
    DocumentStatus,
)
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import (
    AdminInboundDocumentCreateIn,
    DocumentAckDetailsOut,
    DocumentCreateIn,
    DocumentDetailsResponse,
    DocumentFileOut,
    DocumentListItem,
    DocumentOut,
    DocumentRiskSummaryOut,
    DocumentsListResponse,
    DocumentSignIn,
    DocumentSignResult,
    DocumentSignatureOut,
)
from app.domains.documents.timeline_schemas import TimelineEventOut
from app.domains.documents.timeline_service import (
    DocumentTimelineService,
    TimelineActorType,
    TimelineEventType,
    TimelineRequestContext,
)

from app.models.client_actions import DocumentAcknowledgement
from app.models.decision_result import DecisionResult
from app.models.risk_decision import RiskDecision
from app.models.risk_types import RiskDecisionType, RiskSubjectType

_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_LEGACY_DOCUMENT_TYPES = {
    "INVOICE",
    "SUBSCRIPTION_INVOICE",
    "SUBSCRIPTION_ACT",
    "ACT",
    "RECONCILIATION_ACT",
    "CLOSING_PACKAGE",
    "OFFER",
}
_LEGACY_FILE_TYPES_BY_KIND = {
    "PDF": "PDF",
    "XLSX": "XLSX",
}


@dataclass(slots=True)
class DownloadableFile:
    file: DocumentFile
    document: Document


class DocumentsService:
    def __init__(self, repo: DocumentsRepository, storage=None):
        self.repo = repo
        self.storage = storage
        self.timeline = DocumentTimelineService(repo=repo)

    def list_documents(
        self,
        *,
        client_id: str,
        direction: DocumentDirection,
        status: str | None,
        q: str | None,
        limit: int,
        offset: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> DocumentsListResponse:
        rows, total = self.repo.list_documents(
            client_id=client_id,
            direction=direction,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
        )
        document_ids = [str(doc.id) for doc, _files_count in rows]
        try:
            edo_status_by_document = self.repo.list_edo_states_for_documents(document_ids=document_ids)
        except OperationalError:
            edo_status_by_document = {}

        items: list[DocumentListItem] = []
        for doc, files_count in rows:
            action_code = self._action_code_for_document(doc)
            document_id = str(doc.id)
            items.append(
                DocumentListItem(
                    id=document_id,
                    direction=doc.direction,
                    title=doc.title,
                    category=doc.category,
                    doc_type=doc.doc_type,
                    status=doc.status,
                    sender_type=doc.sender_type,
                    sender_name=doc.sender_name,
                    counterparty_name=doc.counterparty_name,
                    number=doc.number,
                    date=doc.date,
                    amount=doc.amount,
                    currency=doc.currency,
                    created_at=doc.created_at,
                    files_count=int(files_count or 0),
                    requires_action=action_code is not None,
                    action_code=action_code,
                    ack_at=self._utc_or_none(getattr(doc, "ack_at", None)),
                    edo_status=edo_status_by_document.get(document_id),
                    period_from=getattr(doc, "period_from", None),
                    period_to=getattr(doc, "period_to", None),
                )
            )
        return DocumentsListResponse(items=items, total=total, limit=limit, offset=offset)

    def create_outbound_draft(
        self,
        *,
        client_id: str,
        data: DocumentCreateIn,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentOut:
        period_from, period_to = self._legacy_period_bounds()
        item = self.repo.create_document(
            id=str(uuid4()),
            tenant_id=0,
            client_id=client_id,
            document_type=self._legacy_document_type(data.doc_type),
            period_from=period_from,
            period_to=period_to,
            version=1,
            direction=DocumentDirection.OUTBOUND.value,
            title=data.title,
            doc_type=data.doc_type,
            description=data.description,
            status=DocumentStatus.DRAFT.value,
        )
        self.timeline.append_event(
            item,
            event_type=TimelineEventType.DOCUMENT_CREATED,
            meta={"direction": DocumentDirection.OUTBOUND.value},
            actor_type=TimelineActorType.USER,
            actor_user_id=actor_user_id,
            request_context=request_context,
        )
        return self._to_document_out(item, [])


    def create_inbound_document_by_admin(
        self,
        *,
        client_id: str,
        data: AdminInboundDocumentCreateIn,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentOut:
        attach_mode = data.attach_mode.upper().strip()
        if attach_mode not in {"UPLOAD", "RENDER"}:
            raise HTTPException(status_code=400, detail="invalid_attach_mode")

        period_from, period_to = self._legacy_period_bounds()
        item = self.repo.create_document(
            id=str(uuid4()),
            tenant_id=0,
            client_id=client_id,
            document_type=self._legacy_document_type(None),
            period_from=period_from,
            period_to=period_to,
            version=1,
            direction=DocumentDirection.INBOUND.value,
            title=data.title,
            category=data.category,
            description=data.description,
            status=DocumentStatus.DRAFT.value,
            sender_type=DocumentSenderType.NEFT.value,
        )
        self.timeline.append_event(
            item,
            event_type=TimelineEventType.DOCUMENT_CREATED,
            meta={
                "direction": DocumentDirection.INBOUND.value,
                "sender_type": DocumentSenderType.NEFT.value,
                "category": item.category,
                "attach_mode": attach_mode,
            },
            actor_type=TimelineActorType.SYSTEM,
            actor_user_id=actor_user_id,
            request_context=request_context,
        )
        return self._to_document_out(item, [])

    async def attach_file(
        self,
        *,
        client_id: str,
        document_id: str,
        upload_file: UploadFile,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentFileOut:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        if document.direction != DocumentDirection.OUTBOUND.value:
            raise HTTPException(status_code=400, detail="invalid_direction")
        if document.status != DocumentStatus.DRAFT.value:
            raise HTTPException(status_code=409, detail="document_not_editable")
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="file_required")

        payload = await upload_file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="file_required")
        if len(payload) > self.max_upload_bytes():
            raise HTTPException(status_code=413, detail="file_too_large")

        mime = upload_file.content_type or "application/octet-stream"
        if mime not in _ALLOWED_MIME:
            raise HTTPException(status_code=415, detail="unsupported_mime")

        legacy_file_type = self._legacy_file_type_for_upload(filename=upload_file.filename, mime=mime)
        if legacy_file_type is None:
            raise HTTPException(status_code=415, detail="unsupported_mime")

        file_id = str(uuid4())
        filename = self.sanitize_filename(upload_file.filename)
        storage_key = f"client/{client_id}/documents/{document_id}/{file_id}/{filename}"
        sha256 = hashlib.sha256(payload).hexdigest()

        if self.storage is None:
            raise RuntimeError("documents_storage_not_configured")
        self.storage.ensure_bucket()
        self.storage.put_object(storage_key, payload, mime)

        item = self.repo.create_document_file(
            id=file_id,
            document_id=document_id,
            file_type=legacy_file_type,
            bucket=getattr(self.storage, "bucket", "client-documents"),
            object_key=storage_key,
            storage_key=storage_key,
            filename=filename,
            mime=mime,
            size=len(payload),
            size_bytes=len(payload),
            content_type=mime,
            sha256=sha256,
        )
        self.timeline.append_event(
            document,
            event_type=TimelineEventType.FILE_UPLOADED,
            meta={
                "file_id": item.id,
                "filename": item.filename,
                "size": item.size,
                "mime": item.mime,
                "sha256": item.sha256,
            },
            actor_type=TimelineActorType.USER,
            actor_user_id=actor_user_id,
            request_context=request_context,
        )
        return self._to_file_out(item)


    async def attach_file_admin_inbound(
        self,
        *,
        document_id: str,
        upload_file: UploadFile,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentFileOut:
        document = self.repo.get_document_by_id(document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        if document.direction != DocumentDirection.INBOUND.value:
            raise HTTPException(status_code=400, detail="invalid_direction")
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="file_required")

        payload = await upload_file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="file_required")
        if len(payload) > self.max_upload_bytes():
            raise HTTPException(status_code=413, detail="file_too_large")

        mime = upload_file.content_type or "application/octet-stream"
        if mime not in _ALLOWED_MIME:
            raise HTTPException(status_code=415, detail="unsupported_mime")

        legacy_file_type = self._legacy_file_type_for_upload(filename=upload_file.filename, mime=mime)
        if legacy_file_type is None:
            raise HTTPException(status_code=415, detail="unsupported_mime")

        file_id = str(uuid4())
        filename = self.sanitize_filename(upload_file.filename)
        storage_key = f"neft/client/{document.client_id}/inbound/{document_id}/{file_id}/{filename}"
        sha256 = hashlib.sha256(payload).hexdigest()

        if self.storage is None:
            raise RuntimeError("documents_storage_not_configured")
        self.storage.ensure_bucket()
        self.storage.put_object(storage_key, payload, mime)

        item = self.repo.create_document_file(
            id=file_id,
            document_id=document_id,
            file_type=legacy_file_type,
            bucket=getattr(self.storage, "bucket", "client-documents"),
            object_key=storage_key,
            storage_key=storage_key,
            filename=filename,
            mime=mime,
            size=len(payload),
            size_bytes=len(payload),
            content_type=mime,
            sha256=sha256,
        )
        self.timeline.append_event(
            document,
            event_type=TimelineEventType.FILE_UPLOADED,
            meta={
                "file_id": item.id,
                "filename": item.filename,
                "size": item.size,
                "mime": item.mime,
                "sha256": item.sha256,
            },
            actor_type=TimelineActorType.SYSTEM,
            actor_user_id=actor_user_id,
            request_context=request_context,
        )
        if document.status != DocumentStatus.READY_TO_SIGN.value:
            previous_status = document.status
            self.repo.update_document_status(document=document, status=DocumentStatus.READY_TO_SIGN.value)
            self.timeline.append_event(
                document,
                event_type=TimelineEventType.STATUS_CHANGED,
                meta={"from": previous_status, "to": DocumentStatus.READY_TO_SIGN.value},
                actor_type=TimelineActorType.SYSTEM,
                actor_user_id=actor_user_id,
                request_context=request_context,
            )
        return self._to_file_out(item)

    def submit_ready_to_send(
        self,
        *,
        client_id: str,
        document_id: str,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentOut:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        if document.direction != DocumentDirection.OUTBOUND.value:
            raise HTTPException(status_code=400, detail="invalid_direction")
        if document.status == DocumentStatus.READY_TO_SEND.value:
            raise HTTPException(status_code=409, detail="already_submitted")
        if document.status != DocumentStatus.DRAFT.value:
            raise HTTPException(status_code=409, detail="document_not_editable")

        files = self.repo.list_document_files(document_id=document_id)
        if not files:
            raise HTTPException(status_code=409, detail="missing_files")

        updated = self.repo.update_document_status(document=document, status=DocumentStatus.READY_TO_SEND.value)
        self.timeline.append_event(
            updated,
            event_type=TimelineEventType.STATUS_CHANGED,
            meta={"from": DocumentStatus.DRAFT.value, "to": DocumentStatus.READY_TO_SEND.value},
            actor_type=TimelineActorType.USER,
            actor_user_id=actor_user_id,
            request_context=request_context,
        )
        return self._to_document_out(updated, files)

    def sign_inbound_document(
        self,
        *,
        client_id: str,
        document_id: str,
        signer_user_id: str,
        payload: DocumentSignIn,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentSignResult:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=403, detail="forbidden")
        if document.direction != DocumentDirection.INBOUND.value:
            raise HTTPException(status_code=409, detail="SIGN_NOT_ALLOWED_FOR_OUTBOUND")
        if document.status not in {DocumentStatus.READY_TO_SIGN.value, DocumentStatus.SIGNED_CLIENT.value, DocumentStatus.CLOSED.value}:
            raise HTTPException(status_code=409, detail="DOC_NOT_READY_TO_SIGN")
        if not payload.checkbox_confirmed:
            raise HTTPException(status_code=400, detail="CHECKBOX_CONFIRMATION_REQUIRED")

        existing = self.repo.get_signature_for_user(document_id=document_id, signer_user_id=signer_user_id, signature_method="SIMPLE")
        if existing is not None:
            return DocumentSignResult(
                document_id=str(document.id),
                status=document.status,
                signed_by_client_at=document.signed_by_client_at,
                signature_id=str(existing.id),
                document_hash_sha256=existing.document_hash_sha256,
            )

        files = self.repo.list_document_files(document_id=document_id)
        if not files:
            raise HTTPException(status_code=409, detail="DOC_FILE_MISSING")
        primary_file = files[0]
        if self.storage is None:
            raise RuntimeError("documents_storage_not_configured")
        try:
            stream = self.storage.get_object_stream(primary_file.storage_key)
            file_bytes = stream.read()
        except Exception as exc:
            raise HTTPException(status_code=409, detail="DOC_FILE_MISSING") from exc
        if not file_bytes:
            raise HTTPException(status_code=409, detail="DOC_FILE_MISSING")

        digest = hashlib.sha256(file_bytes).hexdigest()
        signed_at = datetime.now(timezone.utc)
        signature = self.repo.create_signature(
            id=str(uuid4()),
            document_id=document_id,
            client_id=client_id,
            provider="client_simple_sign",
            signer_user_id=signer_user_id,
            signer_type="CLIENT_USER",
            signature_method="SIMPLE",
            signature_type="ESIGN",
            signature_hash_sha256=digest,
            consent_text_version=payload.consent_text_version,
            document_hash_sha256=digest,
            signed_at=signed_at,
            ip=request_context.ip if request_context else None,
            user_agent=request_context.user_agent if request_context else None,
            payload={
                "checkbox": payload.checkbox_confirmed,
                "full_name": payload.signer_full_name,
                "position": payload.signer_position,
            },
        )

        updated = self.repo.mark_document_signed_by_client(
            document=document,
            signer_user_id=signer_user_id,
            signed_at=signed_at,
            status=DocumentStatus.SIGNED_CLIENT.value,
        )
        self.timeline.append_event(
            updated,
            event_type=TimelineEventType.SIGNED_CLIENT,
            meta={
                "signature_id": str(signature.id),
                "document_hash_sha256": digest,
                "consent_text_version": payload.consent_text_version,
            },
            actor_type=TimelineActorType.USER,
            actor_user_id=signer_user_id,
            request_context=request_context,
        )
        return DocumentSignResult(
            document_id=str(updated.id),
            status=updated.status,
            signed_by_client_at=updated.signed_by_client_at,
            signature_id=str(signature.id),
            document_hash_sha256=digest,
        )

    def list_document_signatures(self, *, client_id: str, document_id: str) -> list[DocumentSignatureOut]:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        items = self.repo.list_signatures(document_id=document_id)
        return [
            DocumentSignatureOut(
                id=str(item.id),
                document_id=str(item.document_id),
                signer_user_id=str(item.signer_user_id),
                signer_type=item.signer_type,
                signature_method=item.signature_method,
                consent_text_version=item.consent_text_version,
                document_hash_sha256=item.document_hash_sha256,
                signed_at=item.signed_at,
                ip=item.ip,
                user_agent=item.user_agent,
                payload=item.payload,
                created_at=item.created_at,
            )
            for item in items
        ]

    def list_timeline_events(self, *, client_id: str, document_id: str) -> list[TimelineEventOut]:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        events = self.repo.list_timeline_events(document_id=document_id)
        return [
            TimelineEventOut(
                id=str(item.id),
                event_type=item.event_type,
                message=item.message,
                meta=item.meta or {},
                actor_type=item.actor_type,
                actor_user_id=str(item.actor_user_id) if item.actor_user_id else None,
                created_at=item.created_at,
            )
            for item in events
        ]

    def get_document_with_files(self, *, client_id: str, document_id: str) -> DocumentOut | None:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            return None
        files = self.repo.list_document_files(document_id=str(document.id))
        return self._to_document_out(document, files)

    def get_file_for_download(self, *, client_id: str, file_id: str) -> DownloadableFile | None:
        row = self.repo.get_file_with_document_for_client(client_id=client_id, file_id=file_id)
        if row is None:
            return None
        file, document = row
        return DownloadableFile(file=file, document=document)

    def get_document(self, *, client_id: str, document_id: str) -> DocumentDetailsResponse | None:
        return self.get_document_with_files(client_id=client_id, document_id=document_id)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        sanitized = _SANITIZE_RE.sub("_", filename.strip())
        return sanitized or "document"

    @staticmethod
    def max_upload_bytes() -> int:
        mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        return mb * 1024 * 1024

    @staticmethod
    def _legacy_document_type(doc_type: str | None) -> str:
        normalized = (doc_type or "").strip().upper()
        if normalized in _LEGACY_DOCUMENT_TYPES:
            return normalized
        return "ACT"

    @staticmethod
    def _legacy_period_bounds() -> tuple[date, date]:
        today = datetime.now(timezone.utc).date()
        return today, today

    @staticmethod
    def _file_kind_from_values(filename: str | None, mime: str | None) -> str:
        mime = (mime or "").lower()
        filename = (filename or "").lower()
        if mime == "application/pdf" or filename.endswith(".pdf"):
            return "PDF"
        if mime in {
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        } or filename.endswith(".xls") or filename.endswith(".xlsx"):
            return "XLSX"
        if mime in {
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        } or filename.endswith(".doc") or filename.endswith(".docx"):
            return "DOC"
        if mime.startswith("image/"):
            return "IMAGE"
        return "OTHER"

    @classmethod
    def _legacy_file_type_for_upload(cls, *, filename: str | None, mime: str | None) -> str | None:
        return _LEGACY_FILE_TYPES_BY_KIND.get(cls._file_kind_from_values(filename, mime))

    @staticmethod
    def _action_code_for_document(document: Document) -> str | None:
        if document.direction == DocumentDirection.OUTBOUND.value:
            if document.status == DocumentStatus.DRAFT.value:
                return "UPLOAD_OR_SUBMIT"
            if document.status == DocumentStatus.READY_TO_SEND.value:
                return "SEND_TO_EDO"
        if document.direction == DocumentDirection.INBOUND.value and document.status == DocumentStatus.READY_TO_SIGN.value:
            return "SIGN"
        return None

    @staticmethod
    def _file_kind(item: DocumentFile) -> str:
        return DocumentsService._file_kind_from_values(item.filename, item.mime)

    def _preferred_document_hash(self, document: Document, files: list[DocumentFile]) -> str | None:
        if document.status in {DocumentStatus.SIGNED_CLIENT.value, DocumentStatus.CLOSED.value, DocumentStatus.SIGNED.value}:
            try:
                signatures = list(getattr(document, "signatures", []) or [])
            except OperationalError:
                signatures = []
            if signatures:
                return signatures[0].document_hash_sha256

        document_hash = getattr(document, "document_hash", None)
        if document_hash:
            return document_hash

        ranked_files = sorted(
            (item for item in files if item.sha256),
            key=lambda item: {"PDF": 0, "XLSX": 1, "DOC": 2, "IMAGE": 3, "OTHER": 4}.get(self._file_kind(item), 99),
        )
        if ranked_files:
            return ranked_files[0].sha256
        return None

    @staticmethod
    def _document_type_value(document: Document) -> str | None:
        document_type = getattr(document, "document_type", None)
        return getattr(document_type, "value", document_type)

    @staticmethod
    def _risk_state(decision: RiskDecisionType | str) -> str:
        decision_value = getattr(decision, "value", decision)
        if decision_value == RiskDecisionType.ALLOW.value:
            return "ALLOW"
        if decision_value == RiskDecisionType.BLOCK.value:
            return "BLOCK"
        return "REQUIRE_OVERRIDE"

    @staticmethod
    def _utc_or_none(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _ack_details_for_document(self, document: Document) -> tuple[datetime | None, DocumentAckDetailsOut | None]:
        ack_at = self._utc_or_none(getattr(document, "ack_at", None))
        document_type = self._document_type_value(document)
        if not document_type:
            return ack_at, None
        try:
            acknowledgement = (
                self.repo.db.query(DocumentAcknowledgement)
                .filter(DocumentAcknowledgement.client_id == document.client_id)
                .filter(DocumentAcknowledgement.document_type == document_type)
                .filter(DocumentAcknowledgement.document_id == str(document.id))
                .one_or_none()
            )
        except OperationalError:
            return ack_at, None
        if acknowledgement is None:
            return ack_at, None
        acknowledgement_ack_at = self._utc_or_none(acknowledgement.ack_at)
        return ack_at or acknowledgement_ack_at, DocumentAckDetailsOut(
            ack_by_user_id=acknowledgement.ack_by_user_id,
            ack_by_email=acknowledgement.ack_by_email,
            ack_ip=acknowledgement.ack_ip,
            ack_user_agent=acknowledgement.ack_user_agent,
            ack_method=acknowledgement.ack_method,
            ack_at=acknowledgement_ack_at,
        )

    def _risk_details_for_document(self, document: Document) -> tuple[DocumentRiskSummaryOut | None, dict | None]:
        try:
            risk_decision = (
                self.repo.db.query(RiskDecision)
                .filter(RiskDecision.subject_type == RiskSubjectType.DOCUMENT)
                .filter(RiskDecision.subject_id == str(document.id))
                .order_by(RiskDecision.decided_at.desc())
                .first()
            )
        except OperationalError:
            return None, None
        if risk_decision is None:
            return None, None

        risk_summary = DocumentRiskSummaryOut(
            state=self._risk_state(risk_decision.outcome),
            decided_at=self._utc_or_none(risk_decision.decided_at),
            decision_id=risk_decision.decision_id,
        )
        try:
            decision_record = (
                self.repo.db.query(DecisionResult)
                .filter(DecisionResult.decision_id == risk_decision.decision_id)
                .one_or_none()
            )
        except OperationalError:
            return risk_summary, None
        return risk_summary, decision_record.explain if decision_record else None

    @staticmethod
    def _to_file_out(item: DocumentFile) -> DocumentFileOut:
        return DocumentFileOut(
            id=str(item.id),
            filename=item.filename,
            mime=item.mime,
            kind=DocumentsService._file_kind(item),
            size=item.size,
            sha256=item.sha256,
            created_at=item.created_at,
        )

    def _to_document_out(self, document: Document, files: list[DocumentFile]) -> DocumentOut:
        action_code = self._action_code_for_document(document)
        ack_at, ack_details = self._ack_details_for_document(document)
        risk, risk_explain = self._risk_details_for_document(document)
        return DocumentOut(
            id=str(document.id),
            client_id=document.client_id,
            direction=document.direction,
            title=document.title,
            category=document.category,
            doc_type=document.doc_type,
            description=document.description,
            status=document.status,
            sender_type=document.sender_type,
            sender_name=document.sender_name,
            counterparty_name=document.counterparty_name,
            counterparty_inn=document.counterparty_inn,
            number=document.number,
            date=document.date,
            amount=document.amount,
            currency=document.currency,
            created_at=document.created_at,
            updated_at=document.updated_at,
            signed_by_client_at=document.signed_by_client_at,
            signed_by_client_user_id=str(document.signed_by_client_user_id) if document.signed_by_client_user_id else None,
            requires_action=action_code is not None,
            action_code=action_code,
            ack_at=ack_at,
            ack_details=ack_details,
            document_hash_sha256=self._preferred_document_hash(document, files),
            risk=risk,
            risk_explain=risk_explain,
            files=[self._to_file_out(item) for item in files],
        )

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.domains.documents.models import Document, DocumentDirection, DocumentFile, DocumentStatus
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import (
    DocumentCreateIn,
    DocumentDetailsResponse,
    DocumentFileOut,
    DocumentListItem,
    DocumentOut,
    DocumentsListResponse,
)
from app.domains.documents.timeline_schemas import TimelineEventOut
from app.domains.documents.timeline_service import (
    DocumentTimelineService,
    TimelineActorType,
    TimelineEventType,
    TimelineRequestContext,
)

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
    ) -> DocumentsListResponse:
        rows, total = self.repo.list_documents(
            client_id=client_id,
            direction=direction,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        items = [
            DocumentListItem(
                id=str(doc.id),
                direction=doc.direction,
                title=doc.title,
                doc_type=doc.doc_type,
                status=doc.status,
                counterparty_name=doc.counterparty_name,
                number=doc.number,
                date=doc.date,
                amount=doc.amount,
                currency=doc.currency,
                created_at=doc.created_at,
                files_count=int(files_count or 0),
            )
            for doc, files_count in rows
        ]
        return DocumentsListResponse(items=items, total=total, limit=limit, offset=offset)

    def create_outbound_draft(
        self,
        *,
        client_id: str,
        data: DocumentCreateIn,
        actor_user_id: str | None = None,
        request_context: TimelineRequestContext | None = None,
    ) -> DocumentOut:
        item = self.repo.create_document(
            id=str(uuid4()),
            client_id=client_id,
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
            storage_key=storage_key,
            filename=filename,
            mime=mime,
            size=len(payload),
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
    def _to_file_out(item: DocumentFile) -> DocumentFileOut:
        return DocumentFileOut(
            id=str(item.id),
            filename=item.filename,
            mime=item.mime,
            size=item.size,
            sha256=item.sha256,
            created_at=item.created_at,
        )

    def _to_document_out(self, document: Document, files: list[DocumentFile]) -> DocumentOut:
        return DocumentOut(
            id=str(document.id),
            client_id=document.client_id,
            direction=document.direction,
            title=document.title,
            doc_type=document.doc_type,
            description=document.description,
            status=document.status,
            counterparty_name=document.counterparty_name,
            counterparty_inn=document.counterparty_inn,
            number=document.number,
            date=document.date,
            amount=document.amount,
            currency=document.currency,
            created_at=document.created_at,
            updated_at=document.updated_at,
            files=[self._to_file_out(item) for item in files],
        )

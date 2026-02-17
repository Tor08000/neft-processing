from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.documents.models import (
    Document,
    DocumentDirection,
    DocumentEdoState,
    DocumentFile,
    DocumentSignature,
    DocumentTimelineEvent,
)


class DocumentsRepository:
    def __init__(self, db: Session):
        self.db = db

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
    ) -> tuple[list[tuple[Document, int]], int]:
        query = (
            self.db.query(Document, func.count(DocumentFile.id).label("files_count"))
            .outerjoin(DocumentFile, DocumentFile.document_id == Document.id)
            .filter(Document.client_id == client_id)
            .filter(Document.direction == direction.value)
        )

        if status:
            query = query.filter(Document.status == status.upper())

        if q:
            pattern = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Document.title.ilike(pattern),
                    Document.number.ilike(pattern),
                    Document.counterparty_name.ilike(pattern),
                )
            )

        if date_from is not None:
            query = query.filter(Document.created_at >= date_from)
        if date_to is not None:
            query = query.filter(Document.created_at <= date_to)

        grouped = query.group_by(Document.id)
        total_query = self.db.query(func.count()).select_from(grouped.subquery())
        total = int(total_query.scalar() or 0)

        items = grouped.order_by(desc(Document.created_at)).offset(offset).limit(limit).all()
        return items, total

    def get_document(self, *, client_id: str, document_id: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .filter(Document.client_id == client_id)
            .one_or_none()
        )

    def create_document(self, **kwargs) -> Document:
        item = Document(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_document_file(self, **kwargs) -> DocumentFile:
        item = DocumentFile(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_document_files(self, *, document_id: str) -> list[DocumentFile]:
        return (
            self.db.query(DocumentFile)
            .filter(DocumentFile.document_id == document_id)
            .order_by(DocumentFile.created_at.desc())
            .all()
        )

    def get_file_with_document_for_client(self, *, client_id: str, file_id: str) -> tuple[DocumentFile, Document] | None:
        row = (
            self.db.query(DocumentFile, Document)
            .join(Document, Document.id == DocumentFile.document_id)
            .filter(DocumentFile.id == file_id)
            .filter(Document.client_id == client_id)
            .one_or_none()
        )
        return row


    def get_signature_for_user(
        self, *, document_id: str, signer_user_id: str, signature_method: str = "SIMPLE"
    ) -> DocumentSignature | None:
        return (
            self.db.query(DocumentSignature)
            .filter(DocumentSignature.document_id == document_id)
            .filter(DocumentSignature.signer_user_id == signer_user_id)
            .filter(DocumentSignature.signature_method == signature_method)
            .one_or_none()
        )

    def list_signatures(self, *, document_id: str) -> list[DocumentSignature]:
        return (
            self.db.query(DocumentSignature)
            .filter(DocumentSignature.document_id == document_id)
            .order_by(DocumentSignature.signed_at.desc())
            .all()
        )

    def create_signature(self, **kwargs) -> DocumentSignature:
        item = DocumentSignature(**kwargs)
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_signature_for_user(
                document_id=str(kwargs.get("document_id")),
                signer_user_id=str(kwargs.get("signer_user_id")),
                signature_method=str(kwargs.get("signature_method") or "SIMPLE"),
            )
            if existing is None:
                raise
            return existing
        self.db.refresh(item)
        return item

    def mark_document_signed_by_client(self, *, document: Document, signer_user_id: str, signed_at: datetime, status: str) -> Document:
        document.signed_by_client_at = signed_at
        document.signed_by_client_user_id = signer_user_id
        document.status = status
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def create_timeline_event(self, **kwargs) -> DocumentTimelineEvent:
        item = DocumentTimelineEvent(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_timeline_events(self, *, document_id: str) -> list[DocumentTimelineEvent]:
        return (
            self.db.query(DocumentTimelineEvent)
            .filter(DocumentTimelineEvent.document_id == document_id)
            .order_by(DocumentTimelineEvent.created_at.desc())
            .all()
        )

    def update_document_status(self, *, document: Document, status: str) -> Document:
        document.status = status
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document


    def get_document_by_id(self, *, document_id: str) -> Document | None:
        return self.db.query(Document).filter(Document.id == document_id).one_or_none()

    def get_edo_state(self, *, document_id: str) -> DocumentEdoState | None:
        return self.db.query(DocumentEdoState).filter(DocumentEdoState.document_id == document_id).one_or_none()

    def get_edo_state_for_client(self, *, client_id: str, document_id: str) -> DocumentEdoState | None:
        return (
            self.db.query(DocumentEdoState)
            .filter(DocumentEdoState.document_id == document_id)
            .filter(DocumentEdoState.client_id == client_id)
            .one_or_none()
        )

    def create_edo_state(self, **kwargs) -> DocumentEdoState:
        item = DocumentEdoState(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save_edo_state(self, item: DocumentEdoState) -> DocumentEdoState:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_edostates_for_poll(self, *, now: datetime, limit: int = 100) -> list[DocumentEdoState]:
        pollable = {"SENT", "QUEUED", "SENDING", "ERROR", "PROVIDER_UNAVAILABLE"}
        return (
            self.db.query(DocumentEdoState)
            .filter(DocumentEdoState.edo_status.in_(pollable))
            .filter(DocumentEdoState.next_poll_at.isnot(None))
            .filter(DocumentEdoState.next_poll_at <= now)
            .order_by(DocumentEdoState.next_poll_at.asc())
            .limit(limit)
            .all()
        )

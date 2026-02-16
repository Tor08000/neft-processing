from __future__ import annotations

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.domains.documents.models import Document, DocumentDirection, DocumentFile, DocumentTimelineEvent


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

from __future__ import annotations

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.domains.documents.models import Document, DocumentDirection, DocumentFile


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

        items = (
            grouped.order_by(desc(Document.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_document(self, *, client_id: str, document_id: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .filter(Document.client_id == client_id)
            .one_or_none()
        )

    def list_document_files(self, *, document_id: str) -> list[DocumentFile]:
        return (
            self.db.query(DocumentFile)
            .filter(DocumentFile.document_id == document_id)
            .order_by(DocumentFile.created_at.desc())
            .all()
        )

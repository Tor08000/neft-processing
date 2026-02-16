from __future__ import annotations

from app.domains.documents.models import DocumentDirection
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import DocumentDetailsResponse, DocumentFileOut, DocumentListItem, DocumentsListResponse


class DocumentsService:
    def __init__(self, repo: DocumentsRepository):
        self.repo = repo

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

    def get_document(self, *, client_id: str, document_id: str) -> DocumentDetailsResponse | None:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            return None
        files = self.repo.list_document_files(document_id=str(document.id))
        return DocumentDetailsResponse(
            id=str(document.id),
            client_id=document.client_id,
            direction=document.direction,
            title=document.title,
            doc_type=document.doc_type,
            status=document.status,
            counterparty_name=document.counterparty_name,
            counterparty_inn=document.counterparty_inn,
            number=document.number,
            date=document.date,
            amount=document.amount,
            currency=document.currency,
            created_at=document.created_at,
            updated_at=document.updated_at,
            files=[
                DocumentFileOut(
                    id=str(item.id),
                    storage_key=item.storage_key,
                    filename=item.filename,
                    mime=item.mime,
                    size=item.size,
                    sha256=item.sha256,
                    created_at=item.created_at,
                )
                for item in files
            ],
        )

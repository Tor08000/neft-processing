from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.generated_docs.models import ClientGeneratedDocument


@dataclass(slots=True)
class ClientGeneratedDocumentsRepository:
    db: Session

    def create_document(self, **kwargs) -> ClientGeneratedDocument:
        now = datetime.now(timezone.utc)
        obj = ClientGeneratedDocument(id=new_uuid_str(), created_at=now, updated_at=now, **kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_by_id(self, doc_id: str) -> ClientGeneratedDocument | None:
        return self.db.get(ClientGeneratedDocument, doc_id)

    def list_by_application_id(self, application_id: str) -> list[ClientGeneratedDocument]:
        stmt = (
            select(ClientGeneratedDocument)
            .where(ClientGeneratedDocument.client_application_id == application_id)
            .order_by(ClientGeneratedDocument.created_at.desc(), ClientGeneratedDocument.doc_kind.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_last_version(self, *, application_id: str | None, client_id: str | None, doc_kind: str) -> int:
        clauses = [ClientGeneratedDocument.doc_kind == doc_kind]
        if application_id:
            clauses.append(ClientGeneratedDocument.client_application_id == application_id)
        if client_id:
            clauses.append(ClientGeneratedDocument.client_id == client_id)
        stmt = select(func.max(ClientGeneratedDocument.version)).where(and_(*clauses))
        return int(self.db.execute(stmt).scalar_one() or 0)


    def mark_client_signed(
        self,
        doc: ClientGeneratedDocument,
        *,
        sign_method: str,
        sign_phone: str | None,
        signature_hash: str,
    ) -> ClientGeneratedDocument:
        now = datetime.now(timezone.utc)
        doc.status = "SIGNED_BY_CLIENT"
        doc.client_signed_at = now
        doc.client_sign_method = sign_method
        doc.client_sign_phone = sign_phone
        doc.client_signature_hash = signature_hash
        doc.updated_at = now
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_status(self, doc: ClientGeneratedDocument, status: str) -> ClientGeneratedDocument:
        doc.status = status
        doc.updated_at = datetime.now(timezone.utc)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

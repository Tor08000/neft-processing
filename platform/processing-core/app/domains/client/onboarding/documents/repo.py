from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.onboarding.documents.models import ClientDocument


@dataclass(slots=True)
class ClientOnboardingDocumentsRepository:
    db: Session

    def create_document(self, **kwargs) -> ClientDocument:
        obj = ClientDocument(id=new_uuid_str(), **kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list_by_application_id(self, application_id: str) -> list[ClientDocument]:
        stmt = (
            select(ClientDocument)
            .where(ClientDocument.client_application_id == application_id)
            .order_by(ClientDocument.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars())

    def get_by_id(self, doc_id: str) -> ClientDocument | None:
        return self.db.get(ClientDocument, doc_id)

    def update_document(self, document: ClientDocument, patch: dict[str, object]) -> ClientDocument:
        for key, value in patch.items():
            setattr(document, key, value)
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_by_id(self, doc_id: str) -> bool:
        obj = self.get_by_id(doc_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True

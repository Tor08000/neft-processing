from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client import Client


@dataclass(slots=True)
class ClientRepository:
    db: Session

    def get_client_by_id(self, client_id: str | None) -> Client | None:
        if not client_id:
            return None
        identity = client_id
        if isinstance(client_id, str):
            try:
                identity = UUID(client_id)
            except ValueError:
                identity = client_id
        return self.db.get(Client, identity)

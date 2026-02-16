from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.client import Client


@dataclass(slots=True)
class ClientRepository:
    db: Session

    def get_client_by_id(self, client_id: str | None) -> Client | None:
        if not client_id:
            return None
        return self.db.get(Client, client_id)

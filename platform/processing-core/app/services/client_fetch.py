from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client import Client


@dataclass(slots=True)
class SafeClient:
    id: str
    name: str | None = None
    external_id: str | None = None
    inn: str | None = None
    status: str | None = None
    created_at: datetime | None = None


def safe_get_client(db: Session, client_id: str) -> dict[str, Any] | None:
    if not client_id:
        return None
    try:
        client_uuid = UUID(str(client_id))
    except (TypeError, ValueError):
        return None
    client = db.get(Client, client_uuid)
    if client is None:
        return None
    return {
        "id": str(client.id),
        "name": client.name,
        "external_id": client.external_id,
        "inn": client.inn,
        "status": client.status,
        "created_at": client.created_at,
    }


def build_safe_client(payload: dict[str, Any]) -> SafeClient:
    return SafeClient(
        id=str(payload.get("id", "")),
        name=payload.get("name"),
        external_id=payload.get("external_id"),
        inn=payload.get("inn"),
        status=payload.get("status"),
        created_at=payload.get("created_at"),
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA


@dataclass(slots=True)
class SafeClient:
    id: str
    name: str | None = None
    external_id: str | None = None
    inn: str | None = None
    status: str | None = None
    created_at: datetime | None = None


def safe_get_client(db: Session, client_id: str) -> dict[str, Any] | None:
    engine = db.get_bind()
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("clients", schema=DB_SCHEMA)}
    if "id" not in columns:
        return None
    clients = Table("clients", MetaData(), schema=DB_SCHEMA, autoload_with=engine)
    select_columns = [clients.c.id]
    for name in ("name", "external_id", "inn", "status", "created_at"):
        if name in columns:
            select_columns.append(clients.c[name])
    stmt = select(*select_columns).where(clients.c.id == str(client_id))
    row = db.execute(stmt).mappings().one_or_none()
    if not row:
        return None
    return dict(row)


def build_safe_client(payload: dict[str, Any]) -> SafeClient:
    return SafeClient(
        id=str(payload.get("id", "")),
        name=payload.get("name"),
        external_id=payload.get("external_id"),
        inn=payload.get("inn"),
        status=payload.get("status"),
        created_at=payload.get("created_at"),
    )

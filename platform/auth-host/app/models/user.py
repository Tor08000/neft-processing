from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass
class User:
    id: str
    email: str
    full_name: str | None
    password_hash: str
    is_active: bool
    created_at: datetime | None
    tenant_id: str | None = None
    status: str = "active"
    token_version: int = 1
    username: str | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "User":
        return cls(
            id=str(row["id"]),
            email=row["email"],
            full_name=row.get("full_name"),
            password_hash=row["password_hash"],
            is_active=bool(row.get("is_active", True)),
            created_at=row.get("created_at"),
            tenant_id=str(row["tenant_id"]) if row.get("tenant_id") else None,
            status=str(row.get("status") or "active"),
            token_version=int(row.get("token_version") or 1),
            username=row.get("username"),
        )

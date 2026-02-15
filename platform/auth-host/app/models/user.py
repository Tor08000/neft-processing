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
            username=row.get("username"),
        )

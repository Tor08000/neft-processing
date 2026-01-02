from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditSigningKeyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str
    alg: str
    public_key_pem: str
    created_at: datetime | None = None
    status: str


class AuditSigningKeysResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[AuditSigningKeyOut]

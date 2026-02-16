from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SSOIdentity:
    user_id: str
    tenant_id: str
    provider_key: str
    external_sub: str
    external_email: str | None = None

from __future__ import annotations

from pydantic import BaseModel


class SSOIdPItem(BaseModel):
    provider_key: str
    display_name: str
    issuer_url: str
    enabled: bool


class SSOIdPListResponse(BaseModel):
    tenant_id: str
    portal: str
    idps: list[SSOIdPItem]


class SSOExchangeRequest(BaseModel):
    code: str

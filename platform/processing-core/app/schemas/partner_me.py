from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PartnerMeUser(BaseModel):
    id: str
    email: str | None = None
    subject_type: str | None = None


class PartnerMeOrg(BaseModel):
    id: str
    name: str | None = None
    status: str | None = None


class PartnerMeResponse(BaseModel):
    user: PartnerMeUser
    org: PartnerMeOrg | None = None
    org_roles: list[str]
    user_roles: list[str]
    entitlements_snapshot: dict[str, Any] | None = None
    capabilities: list[str]

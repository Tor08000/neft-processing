from __future__ import annotations

from pydantic import BaseModel, Field


class PartnerMoneySeedRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    org_name: str = Field(..., min_length=1, max_length=255)
    inn: str = Field(..., min_length=3, max_length=32)


class PartnerMoneySeedResponse(BaseModel):
    partner_org_id: str
    partner_user_email: str

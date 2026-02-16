from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CreateOnboardingApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    phone: str | None = None
    company_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    org_type: str | None = None


class UpdateOnboardingApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    phone: str | None = None
    company_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    org_type: str | None = None


class OnboardingApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    phone: str | None
    company_name: str | None
    inn: str | None
    ogrn: str | None
    org_type: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str | None
    submitted_at: datetime | None
    reviewed_by_user_id: str | None = None
    approved_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    decision_reason: str | None = None
    client_id: str | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None


class CreateOnboardingApplicationResponse(BaseModel):
    application: OnboardingApplicationResponse
    access_token: str

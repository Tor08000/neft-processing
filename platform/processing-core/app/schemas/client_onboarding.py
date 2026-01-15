from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OnboardingStatusResponse(BaseModel):
    step: str
    status: str
    client_type: str | None = None


class OnboardingProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    inn: str | None = Field(default=None, max_length=32)
    kpp: str | None = Field(default=None, max_length=32)
    ogrn: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=512)
    contacts: dict | None = None
    client_type: str | None = Field(default=None, max_length=32)

    model_config = ConfigDict(extra="allow")


class OnboardingProfileResponse(BaseModel):
    step: str
    status: str


class OnboardingContractGenerateResponse(BaseModel):
    contract_id: str
    pdf_url: str
    version: int


class OnboardingContractResponse(BaseModel):
    contract_id: str
    status: str
    pdf_url: str
    version: int


class OnboardingContractSignResponse(BaseModel):
    status: str

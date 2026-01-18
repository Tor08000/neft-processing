from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FixtureScenario = Literal[
    "SCN2_WRONG_AMOUNT",
    "SCN2_UNMATCHED",
    "SCN3_DOUBLE_PAYMENT",
]

FixtureFormat = Literal["CSV", "CLIENT_BANK_1C", "MT940", "ALL"]

WrongAmountMode = Literal["LESS", "MORE"]


class ReconciliationFixtureCreateRequest(BaseModel):
    scenario: FixtureScenario
    invoice_id: str = Field(..., min_length=1, max_length=64)
    org_id: int = Field(..., ge=1)
    format: FixtureFormat
    currency: str = Field(..., min_length=3, max_length=8)
    wrong_amount_mode: WrongAmountMode | None = None
    amount_delta: Decimal | None = Field(default=None, ge=0)
    payer_inn: str | None = Field(default=None, max_length=32)
    payer_name: str | None = Field(default=None, max_length=255)
    seed: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")


class ReconciliationFixtureFile(BaseModel):
    format: Literal["CSV", "CLIENT_BANK_1C", "MT940"]
    file_name: str
    download_url: str


class ReconciliationFixtureBundleResponse(BaseModel):
    bundle_id: str
    files: list[ReconciliationFixtureFile]
    notes: str

    model_config = ConfigDict(extra="forbid")


class ReconciliationFixtureImportCreateRequest(BaseModel):
    format: Literal["CSV", "CLIENT_BANK_1C", "MT940"]
    file_name: str = Field(..., min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")


class ReconciliationFixtureImportCreateResponse(BaseModel):
    import_id: str
    object_key: str

    model_config = ConfigDict(extra="forbid")

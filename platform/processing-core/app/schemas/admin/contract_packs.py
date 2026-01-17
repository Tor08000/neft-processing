from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContractPackGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: int
    format: Literal["PDF", "ZIP"]
    language: Literal["ru", "en"]
    as_of: date
    include_pricing: bool = True
    include_legal_terms: bool = True


class ContractPackGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_pack_id: str
    status: str
    download_url: str
    hash: str
    entitlements_snapshot_hash: str


class ContractPackInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_pack_id: str
    org_id: int
    format: str
    download_url: str
    hash: str
    entitlements_snapshot_hash: str
    as_of: date | None = None
    created_at: datetime | None = None

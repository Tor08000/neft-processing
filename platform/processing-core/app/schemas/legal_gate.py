from __future__ import annotations

from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, Field


class LegalDocumentOut(BaseModel):
    id: str
    code: str
    version: int
    status: str
    effective_from: datetime
    title: str | None = None


class LegalRequiredResponse(BaseModel):
    required: list[LegalDocumentOut]


class LegalAcceptRequest(BaseModel):
    subject_type: str = Field(..., examples=["CLIENT"])
    subject_id: str
    document_ids: list[str] | None = None
    accept_all: bool = False


class LegalAcceptResponse(BaseModel):
    accepted: Sequence[str]

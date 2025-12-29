from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.what_if import defaults


class WhatIfSubjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["INSIGHT", "FUEL_TX", "ORDER", "INVOICE"]
    id: str


class WhatIfEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: WhatIfSubjectIn
    max_candidates: int = Field(default=defaults.MAX_CANDIDATES, ge=1, le=3)


class WhatIfAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str


class WhatIfProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability_improved_pct: int
    expected_effect_label: str
    window_days: int


class WhatIfMemoryBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_size: int
    confidence: float
    window_days: int
    half_life_days: int
    cooldown_reason: str | None = None


class WhatIfMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cooldown: bool
    memory_penalty_pct: int
    basis: WhatIfMemoryBasis


class WhatIfRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outlook: Literal["IMPROVE", "NO_CHANGE", "UNCERTAIN"]
    notes: list[str]


class WhatIfCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    action: WhatIfAction
    projection: WhatIfProjection
    memory: WhatIfMemory
    risk: WhatIfRisk
    what_if_score: float
    explain: list[str]
    deeplink: str | None = None


class WhatIfRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    best_action_code: str
    reason_short: str


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: WhatIfSubjectIn
    candidates: list[WhatIfCandidate]
    recommendation: WhatIfRecommendation | None = None


__all__ = [
    "WhatIfAction",
    "WhatIfCandidate",
    "WhatIfEvaluateRequest",
    "WhatIfMemory",
    "WhatIfProjection",
    "WhatIfRecommendation",
    "WhatIfResponse",
    "WhatIfRisk",
    "WhatIfSubjectIn",
]

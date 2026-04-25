from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Decision = Literal["allow", "review", "deny"]


class ScoreRequest(BaseModel):
    client_id: Optional[str] = Field(default=None, description="Идентификатор клиента")
    card_id: Optional[str] = Field(default=None, description="Токен карты")
    amount: float = Field(gt=0, description="Сумма операции")
    currency: str = Field(default="RUB", description="Валюта операции")
    merchant: Optional[str] = Field(default=None, description="Торговая точка")
    qty: Optional[float] = Field(default=None, description="Количество топлива")
    hour: Optional[int] = Field(default=None, ge=0, le=23, description="Час операции по местному времени")
    metadata: dict = Field(default_factory=dict, description="Дополнительные признаки")


class ScoreResponse(BaseModel):
    score: float = Field(ge=0, le=1)
    decision: Decision
    reason: str
    reasons: List[str] = Field(default_factory=list)
    provider: str = Field(description="Источник скоринга")
    score_source: str = Field(description="Тип скоринга")
    degraded: bool = Field(default=False, description="Явный degraded flag")
    assumptions: List[str] = Field(default_factory=list, description="Допущения при расчёте")
    trace: dict = Field(default_factory=dict, description="Детерминированный trace скоринга")


from .risk_score import (  # noqa: E402
    ExplainFeature,
    ExplainPayload,
    ModelType,
    RiskCategory,
    RiskScoreRequest,
    RiskScoreResponse,
    TrainingRequest,
    TrainingResponse,
)

__all__ = [
    "Decision",
    "ScoreRequest",
    "ScoreResponse",
    "ExplainFeature",
    "ExplainPayload",
    "ModelType",
    "RiskCategory",
    "RiskScoreRequest",
    "RiskScoreResponse",
    "TrainingRequest",
    "TrainingResponse",
]

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

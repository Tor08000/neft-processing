from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelType(str, Enum):
    RISK_SCORE = "risk_score"
    DYNAMIC_LIMITS = "dynamic_limits"
    FRAUD_DETECTION = "fraud_detection"


class RiskCategory(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TrainingRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_type: ModelType
    dataset_ref: Optional[str] = Field(default=None, description="Источник или ссылка на датасет")
    notes: Optional[str] = Field(default=None, description="Дополнительный контекст обучения")
    metrics: Optional[dict] = Field(default=None, description="Метрики обучения (если известны)")


class TrainingResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_type: ModelType
    model_version: str
    status: Literal["trained", "updated"]
    trained_at: datetime
    metrics: dict


class HistoryFeatures(BaseModel):
    operations_count_30d: Optional[int] = Field(default=None, ge=0)
    chargebacks: Optional[int] = Field(default=None, ge=0)
    avg_amount_30d: Optional[float] = Field(default=None, ge=0)


class RiskScoreRequest(BaseModel):
    amount: float = Field(gt=0, description="Сумма транзакции")
    client_score: Optional[float] = Field(default=None, ge=0, le=1, description="Оценка платежеспособности")
    document_type: Literal["invoice", "payout", "credit_note"] = Field(description="Тип документа")
    client_status: Optional[str] = Field(default=None, description="Статус клиента")
    history: Optional[HistoryFeatures] = Field(default=None, description="Исторические признаки")
    metadata: dict = Field(default_factory=dict, description="Дополнительные признаки")


class ExplainFeature(BaseModel):
    feature: str
    value: str | float | int | None
    shap_value: float


class ExplainPayload(BaseModel):
    features: List[ExplainFeature]
    reason: str


class RiskScoreResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    risk_score: int = Field(ge=0, le=100)
    risk_category: RiskCategory
    decision: Literal["ALLOW", "MANUAL_REVIEW", "DECLINE"]
    model_version: str
    explain: ExplainPayload

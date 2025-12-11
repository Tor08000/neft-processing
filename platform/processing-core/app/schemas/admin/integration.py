from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ExternalRequestLogItem(BaseModel):
    id: int
    created_at: datetime
    partner_id: str
    azs_id: Optional[str] = None
    terminal_id: Optional[str] = None
    operation_id: Optional[str] = None
    request_type: str
    amount: Optional[int] = None
    liters: Optional[float] = None
    currency: Optional[str] = None
    status: str
    reason_category: Optional[str] = None
    risk_code: Optional[str] = None
    limit_code: Optional[str] = None


class ExternalRequestLogResponse(BaseModel):
    items: List[ExternalRequestLogItem]
    total: int
    limit: int
    offset: int


class PartnerStatus(BaseModel):
    partner_id: str
    partner_name: str
    status: str
    total_requests: int
    error_rate: float = Field(0, ge=0)
    avg_latency_ms: float = Field(0, ge=0)


class PartnerStatusResponse(BaseModel):
    items: List[PartnerStatus]


class AzsHeatmapItem(BaseModel):
    azs_id: str | None
    total_requests: int
    declines_total: int
    declines_by_category: dict
    error_rate: float


class AzsHeatmapResponse(BaseModel):
    items: List[AzsHeatmapItem]


class DeclineFeedItem(BaseModel):
    id: int
    created_at: datetime
    partner_id: str
    azs_id: str | None
    reason_category: str | None
    risk_code: str | None
    limit_code: str | None
    amount: int | None
    liters: float | None
    operation_id: str | None


class DeclineFeedResponse(BaseModel):
    items: List[DeclineFeedItem]

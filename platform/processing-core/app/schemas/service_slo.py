from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.service_slo import ServiceSloBreachStatus, ServiceSloMetric, ServiceSloService, ServiceSloWindow


class ServiceSloBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: ServiceSloService
    metric: ServiceSloMetric
    objective_json: dict[str, Any]
    window: ServiceSloWindow
    enabled: bool = True


class ServiceSloCreateRequest(ServiceSloBase):
    pass


class ServiceSloUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_json: dict[str, Any] | None = None
    window: ServiceSloWindow | None = None
    enabled: bool | None = None


class ServiceSloOut(ServiceSloBase):
    id: str
    org_id: str
    objective: str | None = None
    breach_status: ServiceSloBreachStatus | None = None
    breached_at: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceSloListResponse(BaseModel):
    items: list[ServiceSloOut]


class ServiceSloBreachOut(BaseModel):
    service: ServiceSloService
    metric: ServiceSloMetric
    objective: str
    window: ServiceSloWindow
    observed: str
    status: ServiceSloBreachStatus
    breached_at: datetime


class ServiceSloBreachListResponse(BaseModel):
    items: list[ServiceSloBreachOut]


__all__ = [
    "ServiceSloBase",
    "ServiceSloBreachListResponse",
    "ServiceSloBreachOut",
    "ServiceSloCreateRequest",
    "ServiceSloListResponse",
    "ServiceSloOut",
    "ServiceSloUpdateRequest",
]

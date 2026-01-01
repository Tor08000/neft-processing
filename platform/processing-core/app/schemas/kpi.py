from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class KpiItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    value: float
    unit: Literal["money", "count", "percent"]
    delta: float | None = None
    good_when: Literal["up", "down", "neutral"]
    target: float | None = None
    progress: float | None = None
    meta: dict[str, Any] | None = None


class KpiSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: int
    as_of: datetime
    kpis: list[KpiItem]


__all__ = ["KpiItem", "KpiSummary"]

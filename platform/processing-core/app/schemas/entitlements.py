from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EntitlementsOut(BaseModel):
    client_id: str
    plan_code: str
    plan_id: str | None = None
    active_price_version_id: str | None = Field(default=None, alias="price_version_id")
    modules: dict[str, dict[str, Any]] = Field(default_factory=dict)
    limits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    pricing: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


__all__ = ["EntitlementsOut"]

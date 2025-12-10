"""Schemas for admin-facing Risk Rule management API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.services.risk_rules import RuleConfig


class RiskRuleBase(BaseModel):
    """Base schema that wraps DSL configuration with optional metadata."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = None
    dsl: RuleConfig


class RiskRuleCreate(RiskRuleBase):
    """Payload to create a new risk rule."""

    pass


class RiskRuleUpdate(RiskRuleBase):
    """Payload to update an existing risk rule."""

    pass


class RiskRuleRead(RiskRuleBase):
    """Representation of a persisted risk rule with audit fields."""

    id: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    version: int


class RiskRuleListResponse(BaseModel):
    """Paginated list of risk rules."""

    items: list[RiskRuleRead]
    total: int
    limit: int
    offset: int


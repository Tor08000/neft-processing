from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


MissionStatus = Literal["ACTIVE", "COMPLETED", "CLAIMED", "EXPIRED"]


class PartnerTierOut(BaseModel):
    partner_id: str
    tier_code: str
    title: str
    score: Decimal
    metrics_snapshot: dict
    evaluated_at: datetime
    benefits: dict
    thresholds: dict


class PartnerMissionOut(BaseModel):
    mission_id: str
    title: str
    description: str | None = None
    rule: dict
    reward: dict
    progress: Decimal
    status: MissionStatus
    updated_at: datetime


class PartnerMissionsResponse(BaseModel):
    items: list[PartnerMissionOut] = Field(default_factory=list)


class PartnerMissionClaimResponse(BaseModel):
    mission_id: str
    status: MissionStatus
    reward: dict


class PartnerBadgeOut(BaseModel):
    badge_id: str
    code: str
    title: str
    description: str | None = None
    icon: str | None = None
    awarded_at: datetime
    expires_at: datetime | None = None


class PartnerLeaderboardEntry(BaseModel):
    partner_id: str
    tier_code: str
    score: Decimal
    metrics_snapshot: dict
    evaluated_at: datetime


class PartnerLeaderboardResponse(BaseModel):
    items: list[PartnerLeaderboardEntry] = Field(default_factory=list)

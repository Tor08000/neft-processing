from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AchievementBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    status: Literal["locked", "in_progress", "unlocked", "blocked"]
    progress: float | None = None
    how_to: str | None = None
    meta: dict[str, Any] | None = None


class AchievementStreak(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    current: int
    target: int
    history: list[bool]
    status: Literal["locked", "in_progress", "unlocked", "blocked"]
    how_to: str | None = None


class AchievementsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: int
    as_of: datetime
    badges: list[AchievementBadge]
    streak: AchievementStreak


__all__ = ["AchievementBadge", "AchievementStreak", "AchievementsSummary"]

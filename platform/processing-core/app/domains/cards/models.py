from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CardLimitDTO:
    limit_type: str
    amount: float
    currency: str = "RUB"
    active: bool = True


@dataclass(slots=True)
class CardTemplateSummaryDTO:
    id: str
    name: str
    is_default: bool


@dataclass(slots=True)
class CardDTO:
    id: str
    status: str
    masked_pan: str | None = None
    issued_at: datetime | None = None
    limits: list[CardLimitDTO] = field(default_factory=list)


@dataclass(slots=True)
class CardsResponseDTO:
    items: list[CardDTO]
    templates: list[CardTemplateSummaryDTO]

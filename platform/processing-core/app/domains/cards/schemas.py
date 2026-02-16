from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LimitUpdate:
    limit_type: str
    amount: float
    currency: str
    active: bool


@dataclass(slots=True)
class CardCreateInput:
    label: str | None
    template_id: str | None

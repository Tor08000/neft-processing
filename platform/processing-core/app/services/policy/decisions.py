from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    policy: str
    reason: str | None = None


__all__ = ["PolicyDecision"]

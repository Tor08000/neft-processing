from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_from_env(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_from_env(value: str | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class RiskV5Config:
    shadow_enabled: bool
    ab_salt: str
    ab_weight_b: int
    scorer_url: str
    scorer_timeout_seconds: float
    registry_url: str


def get_risk_v5_config() -> RiskV5Config:
    """Load the current Risk v5 configuration from environment variables."""

    return RiskV5Config(
        shadow_enabled=_bool_from_env(os.getenv("RISK_V5_SHADOW_ENABLED"), default=False),
        ab_salt=os.getenv("RISK_V5_AB_SALT", "risk_v5_default_salt"),
        ab_weight_b=_int_from_env(os.getenv("RISK_V5_AB_WEIGHT"), default=50),
        scorer_url=os.getenv("RISK_V5_SCORER_URL", "http://ai-service:8000/api/v1/risk-score"),
        scorer_timeout_seconds=_float_from_env(os.getenv("RISK_V5_SCORER_TIMEOUT_SECONDS"), default=2.0),
        registry_url=os.getenv("RISK_V5_REGISTRY_URL", "http://ai-service:8000/api/v1/admin/ai/activate-model"),
    )


__all__ = ["RiskV5Config", "get_risk_v5_config"]

from __future__ import annotations

import httpx

from app.models.risk_types import RiskSubjectType
from app.services.risk_v5.config import get_risk_v5_config


def model_selector(subject_type: RiskSubjectType) -> str:
    return f"risk_v5_{subject_type.value.lower()}"


def activate_model(*, subject_type: RiskSubjectType, model_version: str) -> dict:
    config = get_risk_v5_config()
    payload = {
        "selector": model_selector(subject_type),
        "model_version": model_version,
    }
    with httpx.Client(timeout=config.scorer_timeout_seconds, follow_redirects=True) as client:
        response = client.post(config.registry_url, json=payload)
    response.raise_for_status()
    return response.json()


__all__ = ["activate_model", "model_selector"]

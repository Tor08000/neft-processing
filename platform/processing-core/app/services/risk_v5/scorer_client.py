from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.risk_v5.config import get_risk_v5_config


@dataclass(frozen=True)
class ScorerResponse:
    score: int
    model_version: str | None
    explain: dict | None


def score(*, payload: dict) -> ScorerResponse:
    config = get_risk_v5_config()
    with httpx.Client(timeout=config.scorer_timeout_seconds, follow_redirects=True) as client:
        response = client.post(config.scorer_url, json=payload)
    response.raise_for_status()
    data = response.json()
    return ScorerResponse(
        score=int(data.get("score", 0)),
        model_version=data.get("model_version"),
        explain=data.get("explain"),
    )


__all__ = ["ScorerResponse", "score"]

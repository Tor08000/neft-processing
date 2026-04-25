from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.risk_v5.config import get_risk_v5_config


@dataclass(frozen=True)
class ScorerResponse:
    score: int
    model_version: str | None
    explain: dict | None
    decision: str | None = None


def _parse_score(data: dict) -> int:
    if "risk_score" in data:
        raw_score = data["risk_score"]
    elif "score" in data:
        raw_score = data["score"]
    else:
        raise ValueError("score_missing")
    try:
        numeric_score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("score_invalid") from exc
    if 0 <= numeric_score <= 1:
        numeric_score *= 100
    return int(round(numeric_score))


def score(*, payload: dict) -> ScorerResponse:
    config = get_risk_v5_config()
    with httpx.Client(timeout=config.scorer_timeout_seconds, follow_redirects=True) as client:
        response = client.post(config.scorer_url, json=payload)
    response.raise_for_status()
    data = response.json()
    return ScorerResponse(
        score=_parse_score(data),
        model_version=data.get("model_version"),
        explain=data.get("explain"),
        decision=data.get("decision") or data.get("risk_result"),
    )


__all__ = ["ScorerResponse", "score"]

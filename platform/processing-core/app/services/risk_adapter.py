from __future__ import annotations

import asyncio
import dataclasses
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from neft_shared.logging_setup import get_logger

from app.services import risk_rules

logger = get_logger(__name__)


class RiskDecisionLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    HARD_DECLINE = "HARD_DECLINE"


LEVEL_ORDER = [
    RiskDecisionLevel.LOW,
    RiskDecisionLevel.MEDIUM,
    RiskDecisionLevel.HIGH,
    RiskDecisionLevel.HARD_DECLINE,
]
DEFAULT_SCORE_MAP: Dict[RiskDecisionLevel, float] = {
    RiskDecisionLevel.LOW: 0.2,
    RiskDecisionLevel.MEDIUM: 0.5,
    RiskDecisionLevel.HIGH: 0.8,
    RiskDecisionLevel.HARD_DECLINE: 1.0,
}
AI_SCORE_URL = os.getenv("AI_SCORE_URL", "http://ai-service:8000/v1/ai/score")
AI_SCORE_TIMEOUT_SECONDS = float(os.getenv("AI_SCORE_TIMEOUT_SECONDS", "3.0"))


@dataclass
class OperationContext:
    client_id: UUID
    card_id: UUID
    terminal_id: UUID
    merchant_id: UUID
    product_type: Optional[str] = None
    amount: int = 0
    currency: str = "RUB"
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    geo: Optional[str] = None
    product_id: Optional[str] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None
    tariff_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskResult:
    """Legacy structure produced by rules and some overrides."""

    risk_score: float
    risk_result: str
    reasons: list[str]
    flags: dict[str, Any]
    source: str


@dataclass
class RiskDecision:
    level: RiskDecisionLevel
    rules_fired: list[str]
    reason_codes: list[str]
    ai_score: Optional[float] = None
    ai_model_version: Optional[str] = None


@dataclass
class RiskEvaluation:
    decision: RiskDecision
    score: Optional[float]
    source: str
    flags: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        decision_payload = dataclasses.asdict(self.decision)
        decision_payload["level"] = self.decision.level.value
        payload: dict[str, Any] = {
            "decision": decision_payload,
            "source": self.source,
            "flags": self.flags,
            "reason_codes": list(self.decision.reason_codes),
            "rules_fired": list(self.decision.rules_fired),
        }
        if self.score is not None:
            payload["score"] = self.score
        return payload


def _severity(value: RiskDecisionLevel) -> int:
    try:
        return LEVEL_ORDER.index(value)
    except ValueError:
        return LEVEL_ORDER.index(RiskDecisionLevel.MEDIUM)


def _normalize_level(value: str | None) -> RiskDecisionLevel:
    if not value:
        return RiskDecisionLevel.MEDIUM
    normalized = value.upper()
    if normalized in {"ALLOW", "LOW"}:
        return RiskDecisionLevel.LOW
    if normalized in {"REVIEW", "MEDIUM", "MANUAL_REVIEW"}:
        return RiskDecisionLevel.MEDIUM
    if normalized in {"DENY", "BLOCK", "HARD_DECLINE"}:
        return RiskDecisionLevel.HARD_DECLINE
    if normalized == "HIGH":
        return RiskDecisionLevel.HIGH
    return RiskDecisionLevel.MEDIUM


def _score_bucket(score: float) -> str:
    if score < 0.2:
        return "0.0-0.2"
    if score < 0.5:
        return "0.2-0.5"
    if score < 0.8:
        return "0.5-0.8"
    return "0.8-1.0"


@dataclass
class RiskMetrics:
    latencies_ms: list[float] = field(default_factory=list)
    connection_errors: Counter[str] = field(default_factory=Counter)
    score_distribution: Counter[str] = field(default_factory=Counter)

    def observe_latency(self, value_ms: float) -> None:
        self.latencies_ms.append(value_ms)

    def inc_connection_error(self, kind: str) -> None:
        self.connection_errors[kind] += 1

    def observe_score(self, score: Optional[float]) -> None:
        if score is None:
            return
        bucket = _score_bucket(score)
        self.score_distribution[bucket] += 1

    def reset(self) -> None:
        self.latencies_ms.clear()
        self.connection_errors.clear()
        self.score_distribution.clear()


metrics = RiskMetrics()


async def _post_score(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=AI_SCORE_TIMEOUT_SECONDS) as client:
        response = await client.post(AI_SCORE_URL, json=payload)
    if response.status_code != 200:
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}", request=response.request, response=response
        )
    return response.json()


async def call_risk_engine(context: OperationContext) -> RiskEvaluation:
    payload: Dict[str, Any] = {
        "client_id": str(context.client_id),
        "card_id": str(context.card_id),
        "amount": float(context.amount),
        "currency": context.currency,
        "merchant": str(context.merchant_id),
        "qty": context.quantity,
        "hour": context.created_at.hour,
        "metadata": {
            "terminal_id": str(context.terminal_id),
            "product_type": context.product_type,
            "product_category": context.product_category,
            "mcc": context.mcc,
            "tx_type": context.tx_type,
            "unit_price": context.unit_price,
            "product_id": context.product_id,
            **(context.metadata or {}),
        },
    }

    started_at = time.perf_counter()
    try:
        response_data = await asyncio.wait_for(_post_score(payload), timeout=AI_SCORE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics.observe_latency(latency_ms)
        metrics.inc_connection_error("timeout")
        logger.warning(
            "AI risk scorer timeout", extra={"latency_ms": latency_ms, "payload_keys": list(payload.keys())}
        )
        return RiskEvaluation(
            decision=RiskDecision(
                level=RiskDecisionLevel.MEDIUM, rules_fired=[], reason_codes=[], ai_score=None, ai_model_version=None
            ),
            score=None,
            source="FALLBACK",
            flags={"error": "timeout"},
        )
    except httpx.RequestError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics.observe_latency(latency_ms)
        metrics.inc_connection_error("request_error")
        logger.warning("AI risk scorer connection failed: %s", exc, extra={"latency_ms": latency_ms}, exc_info=exc)
        return RiskEvaluation(
            decision=RiskDecision(
                level=RiskDecisionLevel.MEDIUM, rules_fired=[], reason_codes=[], ai_score=None, ai_model_version=None
            ),
            score=None,
            source="FALLBACK",
            flags={"error": str(exc)},
        )
    except httpx.HTTPStatusError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics.observe_latency(latency_ms)
        metrics.inc_connection_error("bad_status")
        logger.warning(
            "AI risk scorer returned bad status", extra={"status": exc.response.status_code, "latency_ms": latency_ms}
        )
        return RiskEvaluation(
            decision=RiskDecision(
                level=RiskDecisionLevel.MEDIUM, rules_fired=[], reason_codes=[], ai_score=None, ai_model_version=None
            ),
            score=None,
            source="FALLBACK",
            flags={"error": str(exc)},
        )

    latency_ms = (time.perf_counter() - started_at) * 1000
    metrics.observe_latency(latency_ms)
    risk_score = float(
        response_data.get("risk_score")
        if "risk_score" in response_data
        else response_data.get("score", 0.0)
    )
    decision = response_data.get("risk_result") or response_data.get("decision")
    risk_level = _normalize_level(decision)
    reasons = response_data.get("reason_codes") or response_data.get("reasons") or []
    flags = {"ai_payload": response_data}
    ai_model_version = response_data.get("model_version")
    metrics.observe_score(risk_score)
    logger.info(
        "AI risk scorer responded", extra={"latency_ms": latency_ms, "risk_level": risk_level.value, "score": risk_score}
    )

    return RiskEvaluation(
        decision=RiskDecision(
            level=risk_level,
            rules_fired=[],
            reason_codes=list(reasons),
            ai_score=risk_score,
            ai_model_version=ai_model_version,
        ),
        score=risk_score,
        source="AI",
        flags=flags,
    )


def call_risk_engine_sync(context: OperationContext) -> RiskEvaluation:
    return asyncio.run(call_risk_engine(context))


def _rules_to_decision(rules_result: RiskResult) -> RiskDecision:
    rules = []
    if isinstance(rules_result.flags.get("rules"), list):
        rules = [rule.get("name") for rule in rules_result.flags["rules"] if rule.get("name")]
    level = _normalize_level(rules_result.risk_result)
    return RiskDecision(
        level=level,
        rules_fired=rules,
        reason_codes=list(rules_result.reasons),
    )


async def evaluate_risk(context: OperationContext, db=None) -> RiskEvaluation:
    rules_result = await risk_rules.evaluate_rules(context, db=db)
    rules_decision = _rules_to_decision(rules_result)
    combined_flags = dict(rules_result.flags)

    try:
        ai_result = await call_risk_engine(context)
    except Exception as exc:  # pragma: no cover - exercised in tests via fallback
        logger.warning("Risk engine unavailable, using rules only: %s", exc)
        combined_flags["ai_error"] = str(exc)
        return RiskEvaluation(
            decision=rules_decision,
            score=rules_result.risk_score,
            source="RULES_FALLBACK",
            flags=combined_flags,
        )

    if ai_result.source == "FALLBACK" or ai_result.flags.get("error"):
        combined_flags.update(ai_result.flags)
        return RiskEvaluation(
            decision=rules_decision,
            score=rules_result.risk_score,
            source="RULES_FALLBACK",
            flags=combined_flags,
        )

    combined_level = ai_result.decision.level
    if _severity(rules_decision.level) > _severity(combined_level):
        combined_level = rules_decision.level

    combined_score = max(filter(lambda val: val is not None, [ai_result.score, rules_result.risk_score]))
    reason_codes = list(dict.fromkeys([*rules_decision.reason_codes, *ai_result.decision.reason_codes]))
    combined_flags.update(ai_result.flags)

    combined_decision = RiskDecision(
        level=combined_level,
        rules_fired=rules_decision.rules_fired,
        reason_codes=reason_codes,
        ai_score=ai_result.decision.ai_score,
        ai_model_version=ai_result.decision.ai_model_version,
    )

    source = "RULES_AND_AI" if rules_decision.reason_codes else ai_result.source
    return RiskEvaluation(
        decision=combined_decision,
        score=combined_score,
        source=source,
        flags=combined_flags,
    )


def evaluate_risk_sync(context: OperationContext, db=None) -> RiskEvaluation:
    return asyncio.run(evaluate_risk(context, db=db))

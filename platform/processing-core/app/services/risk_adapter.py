from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
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
from neft_shared.settings import get_settings

from app.services import risk_rules
from app.repositories.risk_rules_repository import RiskRulesRepository

logger = get_logger(__name__)


class RiskDecisionLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    HARD_DECLINE = "HARD_DECLINE"


LEVEL_ORDER = [
    RiskDecisionLevel.LOW,
    RiskDecisionLevel.MEDIUM,
    RiskDecisionLevel.HIGH,
    RiskDecisionLevel.MANUAL_REVIEW,
    RiskDecisionLevel.HARD_DECLINE,
]
DEFAULT_SCORE_MAP: Dict[RiskDecisionLevel, float] = {
    RiskDecisionLevel.LOW: 0.2,
    RiskDecisionLevel.MEDIUM: 0.5,
    RiskDecisionLevel.HIGH: 0.8,
    RiskDecisionLevel.MANUAL_REVIEW: 0.6,
    RiskDecisionLevel.HARD_DECLINE: 1.0,
}
AI_SCORE_URL = os.getenv("AI_SCORE_URL", "http://ai-service:8000/api/v1/score/").rstrip("/") + "/"
AI_SCORE_TIMEOUT_SECONDS = float(os.getenv("AI_SCORE_TIMEOUT_SECONDS", "3.0"))
settings = get_settings()


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
    degraded: bool = False
    pipeline: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        decision_payload = dataclasses.asdict(self.decision)
        decision_payload["level"] = self.decision.level.value
        payload: dict[str, Any] = {
            "decision": decision_payload,
            "source": self.source,
            "flags": self.flags,
            "reason_codes": list(self.decision.reason_codes),
            "rules_fired": list(self.decision.rules_fired),
            "degraded": self.degraded,
        }
        if self.score is not None:
            payload["score"] = self.score
        if self.pipeline:
            payload["pipeline"] = self.pipeline
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
        return RiskDecisionLevel.MANUAL_REVIEW
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


def _stable_trace_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _stable_trace_value(value[key])
            for key in sorted(value, key=str)
            if key not in {"latency_ms"}
        }
    if isinstance(value, list):
        return [_stable_trace_value(item) for item in value]
    if isinstance(value, tuple):
        return [_stable_trace_value(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _decision_trace_hash(trace: dict[str, Any]) -> str:
    payload = json.dumps(
        _stable_trace_value(trace),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _attach_decision_trace_hash(flags: dict[str, Any]) -> dict[str, Any]:
    trace = flags.get("decision_trace")
    if isinstance(trace, dict):
        flags["decision_trace_hash"] = _decision_trace_hash(trace)
    return flags


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


def _is_ai_enabled() -> bool:
    """Return whether AI risk evaluation is enabled in configuration."""

    value = getattr(settings, "AI_RISK_ENABLED", True)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _rules_source() -> str:
    """Return configured rules source (``DB`` or ``CODE``)."""

    value = getattr(settings, "RISK_RULES_SOURCE", "CODE") or "CODE"
    return str(value).upper()


async def _post_score(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=AI_SCORE_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.post(AI_SCORE_URL, json=payload)
    if response.status_code != 200:
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}", request=response.request, response=response
        )
    return response.json()


def _build_ai_fallback(
    *,
    error_type: str,
    error_detail: str,
    latency_ms: float,
    retryable: bool,
    response_data: dict[str, Any] | None = None,
) -> RiskEvaluation:
    flags: dict[str, Any] = {
        "error": error_detail,
        "error_type": error_type,
        "retryable": retryable,
        "degraded": True,
        "provider": "ai-service",
    }
    if response_data is not None:
        flags["ai_payload"] = response_data
    return RiskEvaluation(
        decision=RiskDecision(
            level=RiskDecisionLevel.MEDIUM,
            rules_fired=[],
            reason_codes=[f"ai_{error_type}"],
            ai_score=None,
            ai_model_version=None,
        ),
        score=None,
        source="FALLBACK",
        flags=flags,
        degraded=True,
        pipeline={
            "stage": "ai_score",
            "provider": "ai-service",
            "status": "degraded",
            "error_type": error_type,
            "retryable": retryable,
            "latency_ms": round(latency_ms, 3),
        },
    )


def _parse_ai_response(response_data: dict[str, Any]) -> tuple[float, str, list[str], str | None]:
    raw_score = response_data.get("risk_score")
    if raw_score is None:
        raw_score = response_data.get("score")
    if raw_score is None:
        raise ValueError("score_missing")
    try:
        risk_score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("score_invalid") from exc
    decision = response_data.get("risk_result") or response_data.get("decision")
    if not decision:
        raise ValueError("decision_missing")
    raw_reasons = response_data.get("reason_codes") or response_data.get("reasons") or []
    if not isinstance(raw_reasons, list):
        raise ValueError("reason_codes_invalid")
    reasons = [str(item) for item in raw_reasons if item]
    return risk_score, str(decision), reasons, response_data.get("model_version")


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
        return _build_ai_fallback(
            error_type="timeout",
            error_detail="timeout",
            latency_ms=latency_ms,
            retryable=True,
        )
    except httpx.RequestError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics.observe_latency(latency_ms)
        metrics.inc_connection_error("request_error")
        logger.warning("AI risk scorer connection failed: %s", exc, extra={"latency_ms": latency_ms}, exc_info=exc)
        return _build_ai_fallback(
            error_type="request_error",
            error_detail=str(exc),
            latency_ms=latency_ms,
            retryable=True,
        )
    except httpx.HTTPStatusError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics.observe_latency(latency_ms)
        metrics.inc_connection_error("bad_status")
        logger.warning(
            "AI risk scorer returned bad status", extra={"status": exc.response.status_code, "latency_ms": latency_ms}
        )
        return _build_ai_fallback(
            error_type="bad_status",
            error_detail=str(exc),
            latency_ms=latency_ms,
            retryable=False,
        )

    latency_ms = (time.perf_counter() - started_at) * 1000
    metrics.observe_latency(latency_ms)
    try:
        risk_score, decision, reasons, ai_model_version = _parse_ai_response(response_data)
    except ValueError as exc:
        metrics.inc_connection_error("malformed_response")
        logger.warning(
            "AI risk scorer returned malformed payload",
            extra={"error_type": str(exc), "latency_ms": latency_ms},
        )
        return _build_ai_fallback(
            error_type="malformed_response",
            error_detail=str(exc),
            latency_ms=latency_ms,
            retryable=False,
            response_data=response_data,
        )

    risk_level = _normalize_level(decision)
    flags = {"ai_payload": response_data, "provider": "ai-service"}
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
        degraded=False,
        pipeline={
            "stage": "ai_score",
            "provider": "ai-service",
            "status": "ok",
            "latency_ms": round(latency_ms, 3),
            "model_version": ai_model_version,
        },
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


def _load_rules_from_db(
    context: OperationContext, db
) -> list[risk_rules.RuleDefinition]:
    """Load applicable rules for the context from the database.

    The selection aggregates global rules with scoped ones for the client, card,
    and tariff (when provided). Duplicates by name are ignored and the result is
    sorted by priority to preserve deterministic execution order.
    """

    if db is None:
        return []

    repository = RiskRulesRepository(db)
    scoped_targets: list[tuple[risk_rules.RuleScope, str | None]] = [
        (risk_rules.RuleScope.GLOBAL, None),
        (risk_rules.RuleScope.CLIENT, str(context.client_id)),
        (risk_rules.RuleScope.CARD, str(context.card_id)),
    ]
    if context.tariff_id:
        scoped_targets.append((risk_rules.RuleScope.TARIFF, str(context.tariff_id)))

    rules: list[risk_rules.RuleDefinition] = []
    seen_names: set[str] = set()
    for scope, subject_ref in scoped_targets:
        for definition in repository.get_active_rules_by_scope(scope, subject_ref):
            if definition.name in seen_names:
                continue
            seen_names.add(definition.name)
            rules.append(definition)

    return sorted(rules, key=lambda rule: rule.priority)


async def evaluate_risk(context: OperationContext, db=None) -> RiskEvaluation:
    rules_from_db: list[risk_rules.RuleDefinition] | None = None
    if _rules_source() == "DB":
        loaded_rules = _load_rules_from_db(context, db)
        if loaded_rules:
            rules_from_db = loaded_rules
        else:
            logger.info(
                "Risk rules source is DB but no persisted rules found; falling back to code defaults",
                extra={"client_id": str(context.client_id)},
            )

    rules_result = await risk_rules.evaluate_rules(context, db=db, rules=rules_from_db)
    rules_decision = _rules_to_decision(rules_result)
    combined_flags = dict(rules_result.flags)
    combined_flags["decision_trace"] = {
        "rules": {
            "source": rules_result.source,
            "risk_score": rules_result.risk_score,
            "level": rules_decision.level.value,
            "reason_codes": list(rules_decision.reason_codes),
        },
        "ai_enabled": _is_ai_enabled(),
    }

    experimental_rule_set = getattr(settings, "RISK_EXPERIMENTAL_RULE_SET", "")
    if experimental_rule_set:
        combined_flags.setdefault("config", {})["experimental_rule_set"] = experimental_rule_set

    if not _is_ai_enabled():
        combined_flags["ai_disabled"] = True
        combined_flags["decision_trace"]["result"] = {"source": "RULES_ONLY", "degraded": False}
        _attach_decision_trace_hash(combined_flags)
        return RiskEvaluation(
            decision=rules_decision,
            score=rules_result.risk_score,
            source="RULES_ONLY",
            flags=combined_flags,
        )

    try:
        ai_result = await call_risk_engine(context)
    except Exception as exc:  # pragma: no cover - exercised in tests via fallback
        logger.warning("Risk engine unavailable, using rules only: %s", exc)
        combined_flags["ai_error"] = str(exc)
        combined_flags["ai_error_type"] = "exception"
        combined_flags["decision_trace"]["result"] = {"source": "RULES_FALLBACK", "degraded": True}
        _attach_decision_trace_hash(combined_flags)
        return RiskEvaluation(
            decision=rules_decision,
            score=rules_result.risk_score,
            source="RULES_FALLBACK",
            flags=combined_flags,
            degraded=True,
        )

    combined_flags["decision_trace"]["ai"] = {
        "source": ai_result.source,
        "degraded": ai_result.degraded,
        "reason_codes": list(ai_result.decision.reason_codes),
        "pipeline": ai_result.pipeline,
    }

    if ai_result.source == "FALLBACK" or ai_result.flags.get("error") or ai_result.degraded:
        combined_flags.update(ai_result.flags)
        combined_flags["ai_error_type"] = ai_result.flags.get("error_type")
        combined_flags["decision_trace"]["result"] = {"source": "RULES_FALLBACK", "degraded": True}
        _attach_decision_trace_hash(combined_flags)
        return RiskEvaluation(
            decision=rules_decision,
            score=rules_result.risk_score,
            source="RULES_FALLBACK",
            flags=combined_flags,
            degraded=True,
            pipeline=ai_result.pipeline,
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
    combined_flags["decision_trace"]["result"] = {"source": source, "degraded": False}
    _attach_decision_trace_hash(combined_flags)
    return RiskEvaluation(
        decision=combined_decision,
        score=combined_score,
        source=source,
        flags=combined_flags,
        degraded=False,
        pipeline={
            "stage": "risk_evaluation",
            "status": "ok",
            "rules_level": rules_decision.level.value,
            "ai_level": ai_result.decision.level.value,
            "combined_level": combined_level.value,
        },
    )


def evaluate_risk_sync(context: OperationContext, db=None) -> RiskEvaluation:
    return asyncio.run(evaluate_risk(context, db=db))

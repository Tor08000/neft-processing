from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from neft_shared.logging_setup import get_logger

from app.services import risk_rules

logger = get_logger(__name__)


LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "BLOCK", "MANUAL_REVIEW"]
DEFAULT_SCORE_MAP: Dict[str, float] = {
    "LOW": 0.2,
    "MEDIUM": 0.5,
    "HIGH": 0.8,
    "BLOCK": 1.0,
    "MANUAL_REVIEW": 0.6,
}


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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskResult:
    risk_score: float
    risk_result: str
    reasons: list[str]
    flags: dict[str, Any]
    source: str


def _severity(value: str) -> int:
    try:
        return LEVEL_ORDER.index(value.upper())
    except ValueError:
        return LEVEL_ORDER.index("MEDIUM")


def _map_decision(decision: str | None) -> str:
    if not decision:
        return "MEDIUM"
    normalized = decision.upper()
    if normalized in {"ALLOW", "LOW"}:
        return "LOW"
    if normalized in {"REVIEW", "MEDIUM", "MANUAL_REVIEW"}:
        return "MEDIUM"
    if normalized in {"DENY", "BLOCK"}:
        return "BLOCK"
    if normalized == "HIGH":
        return "HIGH"
    return "MEDIUM"


async def _post_score(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post("http://ai-service:8000/api/v1/score", json=payload)
    if response.status_code != 200:
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}", request=response.request, response=response
        )
    return response.json()


async def call_risk_engine(context: OperationContext) -> RiskResult:
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

    response_data = await _post_score(payload)
    risk_score = float(
        response_data.get("risk_score")
        if "risk_score" in response_data
        else response_data.get("score", 0.0)
    )
    decision = response_data.get("risk_result") or response_data.get("decision")
    risk_result = _map_decision(decision)
    reasons = response_data.get("reasons") or []
    flags = {"ai_payload": response_data}
    return RiskResult(
        risk_score=risk_score,
        risk_result=risk_result,
        reasons=reasons,
        flags=flags,
        source="AI",
    )


def call_risk_engine_sync(context: OperationContext) -> RiskResult:
    return asyncio.run(call_risk_engine(context))


async def evaluate_risk(context: OperationContext, db=None) -> RiskResult:
    rules_result = await risk_rules.evaluate_rules(context, db=db)

    try:
        ai_result = await call_risk_engine(context)
    except Exception as exc:  # pragma: no cover - exercised in tests via fallback
        logger.warning("Risk engine unavailable, using rules only: %s", exc)
        flags = {**rules_result.flags, "ai_error": str(exc)}
        return RiskResult(
            risk_score=rules_result.risk_score,
            risk_result=rules_result.risk_result,
            reasons=rules_result.reasons,
            flags=flags,
            source="RULES_FALLBACK",
        )

    # If AI responded with fallback marker, rely on rules
    if ai_result.source == "FALLBACK" or ai_result.flags.get("error"):
        flags = {**rules_result.flags, **ai_result.flags}
        return RiskResult(
            risk_score=rules_result.risk_score,
            risk_result=rules_result.risk_result,
            reasons=rules_result.reasons,
            flags=flags,
            source="RULES_FALLBACK",
        )

    combined_level = (
        ai_result.risk_result
        if _severity(ai_result.risk_result) > _severity(rules_result.risk_result)
        else rules_result.risk_result
    )
    combined_score = max(ai_result.risk_score, rules_result.risk_score)
    combined_reasons = [*rules_result.reasons, *ai_result.reasons]
    combined_flags = {**rules_result.flags, **ai_result.flags}

    source = "AI+RULES"
    return RiskResult(
        risk_score=combined_score,
        risk_result=combined_level,
        reasons=combined_reasons,
        flags=combined_flags,
        source=source,
    )


def evaluate_risk_sync(context: OperationContext, db=None) -> RiskResult:
    return asyncio.run(evaluate_risk(context, db=db))

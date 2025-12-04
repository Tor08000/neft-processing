from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Dict, Optional

import httpx

from neft_shared.logging_setup import get_logger

from app.models.operation import RiskResult

logger = get_logger(__name__)

RISK_HIGH_THRESHOLD = int(os.getenv("RISK_HIGH_THRESHOLD", "100000"))
RISK_NIGHT_HOUR = 23


@dataclass
class OperationContext:
    client_id: str
    card_id: str
    terminal_id: str
    merchant_id: str
    amount: int
    currency: str
    product_id: Optional[str] = None
    product_type: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _apply_stub_rules(amount: int, ts: Optional[datetime] = None) -> tuple[RiskResult, dict]:
    ts = ts or datetime.now(timezone.utc)
    threshold = int(os.getenv("RISK_HIGH_THRESHOLD", str(RISK_HIGH_THRESHOLD)))
    result = RiskResult.LOW

    if amount >= threshold:
        result = RiskResult.HIGH

    if ts.time() >= time(RISK_NIGHT_HOUR, 0) and amount > threshold // 2:
        result = RiskResult.HIGH

    payload = {
        "engine": "rule_stub",
        "evaluated_at": ts.isoformat(),
        "threshold": threshold,
    }
    return result, payload


def _map_decision(decision: str | None) -> RiskResult:
    if not decision:
        return RiskResult.MEDIUM
    normalized = decision.upper()
    if normalized in {"ALLOW", "LOW"}:
        return RiskResult.LOW
    if normalized in {"REVIEW", "MEDIUM"}:
        return RiskResult.MEDIUM
    if normalized in {"DENY", "BLOCK"}:
        return RiskResult.BLOCK
    if normalized == "HIGH":
        return RiskResult.HIGH
    return RiskResult.MEDIUM


async def _post_score(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post("http://ai-service:8000/api/v1/score", json=payload)
    if response.status_code != 200:
        raise httpx.HTTPStatusError(
            f"Unexpected status {response.status_code}", request=response.request, response=response
        )
    return response.json()


async def call_risk_engine(context: OperationContext) -> tuple[RiskResult, float, dict]:
    payload: Dict[str, Any] = {
        "client_id": context.client_id,
        "card_id": context.card_id,
        "amount": float(context.amount),
        "currency": context.currency,
        "merchant": context.merchant_id,
        "qty": context.quantity,
        "hour": context.timestamp.hour,
        "metadata": {
            "terminal_id": context.terminal_id,
            "product_type": context.product_type,
            "product_category": context.product_category,
            "mcc": context.mcc,
            "tx_type": context.tx_type,
            "unit_price": context.unit_price,
            "product_id": context.product_id,
        },
    }

    try:
        response_data = await _post_score(payload)
        risk_score = float(
            response_data.get("risk_score")
            if "risk_score" in response_data
            else response_data.get("score", 0.0)
        )
        decision = response_data.get("risk_result") or response_data.get("decision")
        risk_result = _map_decision(decision)
        return risk_result, risk_score, response_data
    except Exception as exc:  # pragma: no cover - handled by fallback
        logger.warning("Risk engine unavailable, using fallback: %s", exc)
        stub_result, stub_payload = _apply_stub_rules(context.amount, context.timestamp)
        fallback_result = RiskResult.HIGH if stub_result == RiskResult.HIGH else RiskResult.MEDIUM
        fallback_payload = {
            "fallback": True,
            "error": str(exc),
            "stub": stub_payload,
        }
        return fallback_result, 0.5, fallback_payload


def call_risk_engine_sync(context: OperationContext) -> tuple[RiskResult, float, dict]:
    return asyncio.run(call_risk_engine(context))

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Set

from neft_shared.logging_setup import get_logger
from sqlalchemy.orm import Session

from app.models.operation import Operation

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from app.services.risk_adapter import OperationContext, RiskResult

logger = get_logger(__name__)

AMOUNT_THRESHOLD = int(os.getenv("RISK_AMOUNT_THRESHOLD", "100000"))
GRAYLIST_TERMINALS = set(filter(None, os.getenv("RISK_GRAYLIST_TERMINALS", "").split(",")))
GRAYLIST_MERCHANTS = set(filter(None, os.getenv("RISK_GRAYLIST_MERCHANTS", "").split(",")))
NIGHT_START = int(os.getenv("RISK_NIGHT_START", "0"))
NIGHT_END = int(os.getenv("RISK_NIGHT_END", "5"))
HIGH_FREQUENCY_THRESHOLD = int(os.getenv("RISK_HIGH_FREQUENCY_THRESHOLD", "5"))

LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "BLOCK", "MANUAL_REVIEW"]
SCORE_MAP: Dict[str, float] = {
    "LOW": 0.2,
    "MEDIUM": 0.5,
    "HIGH": 0.8,
    "BLOCK": 1.0,
    "MANUAL_REVIEW": 0.6,
}


@dataclass
class RecentStats:
    avg_amount: float = 0.0
    max_amount: int = 0
    operations_count_last_24h: int = 0
    operations_count_last_hour: int = 0
    usual_product_types: Set[str] | None = None


def _severity(value: str) -> int:
    try:
        return LEVEL_ORDER.index(value.upper())
    except ValueError:
        return LEVEL_ORDER.index("MEDIUM")


def _raise_level(current: str, desired: str) -> str:
    return desired if _severity(desired) > _severity(current) else current


def _compute_score(level: str, reasons: Iterable[str]) -> float:
    base = SCORE_MAP.get(level.upper(), SCORE_MAP["MEDIUM"])
    bump = min(0.2, 0.05 * len(list(reasons)))
    return min(1.0, base + bump)


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def load_recent_operations_stats(
    db: Optional[Session], card_id: Any, client_id: Any, now: Optional[datetime] = None
) -> RecentStats:
    if db is None:
        return RecentStats()

    now = now or datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    last_day = now - timedelta(days=1)
    last_hour = now - timedelta(hours=1)

    base_query = db.query(Operation).filter(
        Operation.card_id == str(card_id),
        Operation.client_id == str(client_id),
        Operation.created_at >= month_ago,
    )

    operations = base_query.all()
    if not operations:
        return RecentStats()

    for op in operations:
        op.created_at = _normalize_dt(op.created_at)

    amounts = [op.amount for op in operations]
    avg_amount = sum(amounts) / len(amounts)
    max_amount = max(amounts)

    ops_last_day = [op for op in operations if op.created_at >= last_day]
    ops_last_hour = [op for op in operations if op.created_at >= last_hour]
    usual_product_types = {op.product_type for op in operations if op.product_type}

    return RecentStats(
        avg_amount=avg_amount,
        max_amount=max_amount,
        operations_count_last_24h=len(ops_last_day),
        operations_count_last_hour=len(ops_last_hour),
        usual_product_types=usual_product_types,
    )


async def evaluate_rules(
    context: "OperationContext", db=None
) -> "RiskResult":
    # Lazy import to avoid circular dependency
    from app.services.risk_adapter import RiskResult

    reasons: list[str] = []
    flags: dict[str, Any] = {}
    level = "LOW"

    amount_threshold = int(
        os.getenv(
            "RISK_AMOUNT_THRESHOLD",
            os.getenv("RISK_HIGH_THRESHOLD", str(AMOUNT_THRESHOLD)),
        )
    )
    graylist_terminals = GRAYLIST_TERMINALS or set(
        filter(None, os.getenv("RISK_GRAYLIST_TERMINALS", "").split(","))
    )
    graylist_merchants = GRAYLIST_MERCHANTS or set(
        filter(None, os.getenv("RISK_GRAYLIST_MERCHANTS", "").split(","))
    )
    night_start = int(os.getenv("RISK_NIGHT_START", str(NIGHT_START)))
    night_end = int(os.getenv("RISK_NIGHT_END", str(NIGHT_END)))
    frequency_threshold = int(
        os.getenv("RISK_HIGH_FREQUENCY_THRESHOLD", str(HIGH_FREQUENCY_THRESHOLD))
    )

    # Amount threshold
    if context.amount >= amount_threshold:
        level = _raise_level(level, "MEDIUM")
        reasons.append("amount_above_threshold")
        flags["amount_threshold_hit"] = True

    # Night operations
    if night_start <= context.created_at.hour < night_end:
        reasons.append("night_operation")
        flags["night"] = True
        if context.amount > amount_threshold // 2:
            level = _raise_level(level, "MEDIUM")

    # Graylist checks
    if str(context.terminal_id) in graylist_terminals:
        level = _raise_level(level, "HIGH")
        reasons.append("graylisted_terminal")
        flags["graylisted_terminal"] = True
    if str(context.merchant_id) in graylist_merchants:
        level = _raise_level(level, "HIGH")
        reasons.append("graylisted_merchant")
        flags["graylisted_merchant"] = True

    # Recent history based anomalies
    stats = await load_recent_operations_stats(db, context.card_id, context.client_id, context.created_at)
    if stats.max_amount and context.amount > stats.max_amount * 2:
        level = _raise_level(level, "HIGH")
        reasons.append("amount_spike")
        flags["amount_spike"] = {
            "max_amount": stats.max_amount,
            "current_amount": context.amount,
        }
    if stats.operations_count_last_hour > frequency_threshold:
        level = _raise_level(level, "HIGH")
        reasons.append("high_frequency")
        flags["frequency_last_hour"] = stats.operations_count_last_hour
    if context.product_type and stats.usual_product_types is not None:
        if context.product_type not in stats.usual_product_types:
            level = _raise_level(level, "MEDIUM")
            reasons.append("unusual_fuel_type")
            flags["unusual_product_type"] = context.product_type

    risk_score = _compute_score(level, reasons)
    return RiskResult(
        risk_score=risk_score,
        risk_result=level,
        reasons=reasons,
        flags=flags,
        source="RULES",
    )

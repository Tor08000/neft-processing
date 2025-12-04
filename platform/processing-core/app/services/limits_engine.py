from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.limit_rule import FuelProductType, LimitRule, LimitScope
from app.models.operation import Operation

if TYPE_CHECKING:
    from app.services.limits import CheckAndReserveRequest

DEFAULT_DAILY_LIMIT = 1_000_000
DEFAULT_PER_TX_LIMIT = 50_000


def _phase_matches(rule: LimitRule, phase: str) -> bool:
    if not rule.phase:
        return True
    if rule.phase.upper() == "BOTH":
        return True
    return rule.phase.upper() == phase.upper()


def rule_matches(rule: LimitRule, request: "CheckAndReserveRequest") -> bool:
    if hasattr(rule, "active") and rule.active is False:
        return False

    if not _phase_matches(rule, request.phase):
        return False

    for attr in (
        "client_id",
        "card_id",
        "merchant_id",
        "terminal_id",
        "client_group_id",
        "card_group_id",
        "product_category",
        "product_type",
        "mcc",
        "tx_type",
    ):
        value = getattr(rule, attr)
        if value is not None and value != getattr(request, attr):
            return False

    return True


def rule_specificity(rule: LimitRule, request: "CheckAndReserveRequest") -> Tuple[int, ...]:
    return (
        int(bool(rule.phase and rule.phase.upper() == request.phase.upper())),
        int(bool(rule.client_id and rule.client_id == request.client_id)),
        int(bool(rule.card_id and rule.card_id == request.card_id)),
        int(bool(rule.client_group_id and rule.client_group_id == request.client_group_id)),
        int(bool(rule.card_group_id and rule.card_group_id == request.card_group_id)),
        int(bool(rule.merchant_id and rule.merchant_id == request.merchant_id)),
        int(bool(rule.terminal_id and rule.terminal_id == request.terminal_id)),
        int(bool(rule.product_category and rule.product_category == request.product_category)),
        int(bool(rule.product_type and rule.product_type == getattr(request, "product_type", None))),
        int(bool(rule.mcc and rule.mcc == request.mcc)),
        int(bool(rule.tx_type and rule.tx_type == request.tx_type)),
    )


def select_best_rule(
    request: "CheckAndReserveRequest", rules: Sequence[LimitRule]
) -> Optional[LimitRule]:
    applicable = [rule for rule in rules if rule_matches(rule, request)]
    if not applicable:
        return None

    return max(applicable, key=lambda r: rule_specificity(r, request))


def calculate_used_amount(db: Session, request: "CheckAndReserveRequest") -> int:
    today = datetime.now(timezone.utc).date()

    target_operation_type = "AUTH" if request.phase.upper() == "AUTH" else "CAPTURE"
    query = db.query(func.coalesce(func.sum(Operation.amount), 0)).filter(
        Operation.operation_type == target_operation_type
    )

    if request.card_id:
        query = query.filter(Operation.card_id == request.card_id)
    if request.client_id:
        query = query.filter(Operation.client_id == request.client_id)
    if request.merchant_id:
        query = query.filter(Operation.merchant_id == request.merchant_id)
    if request.terminal_id:
        query = query.filter(Operation.terminal_id == request.terminal_id)

    query = query.filter(func.date(Operation.created_at) == today)

    return int(query.scalar() or 0)


def evaluate_limits(
    request: "CheckAndReserveRequest",
    rules: Iterable[LimitRule],
    *,
    used_today: int = 0,
):
    rule = select_best_rule(request, list(rules))

    daily_limit = rule.daily_limit if rule and rule.daily_limit is not None else DEFAULT_DAILY_LIMIT
    limit_per_tx = rule.limit_per_tx if rule and rule.limit_per_tx is not None else DEFAULT_PER_TX_LIMIT

    if rule and rule.max_amount is not None:
        if rule.scope == LimitScope.PER_TX:
            limit_per_tx = rule.max_amount
        elif rule.scope == LimitScope.DAILY:
            daily_limit = rule.max_amount

    new_used_today = used_today + request.amount

    approved = request.amount <= limit_per_tx and new_used_today <= daily_limit

    return {
        "approved": approved,
        "response_code": "00" if approved else "51",
        "response_message": "approved" if approved else "limit exceeded",
        "daily_limit": daily_limit,
        "limit_per_tx": limit_per_tx,
        "used_today": used_today,
        "new_used_today": new_used_today,
        "applied_rule_id": rule.id if rule else None,
    }

from dataclasses import dataclass
from typing import Callable

from app.services.decision.context import DecisionContext
from app.services.decision.result import DecisionOutcome
from app.services.decision.rules.scoring_rules import (
    Rule as ScoringRule,
    apply_scoring_rules,
    default_scoring_rules,
)
from app.services.decision.versions import DecisionAction

DEFAULT_SINGLE_TX_LIMIT = 10_000_000
FINALIZED_PERIOD_STATUSES = {"FINALIZED", "LOCKED"}
BLOCKED_CLIENT_STATUSES = {"BLOCKED", "SUSPENDED", "INACTIVE"}


@dataclass(frozen=True)
class Rule:
    id: str
    when: Callable[[DecisionContext], bool]
    outcome: DecisionOutcome
    explain: str


def _single_transaction_limit(ctx: DecisionContext) -> bool:
    limit = ctx.metadata.get("single_transaction_limit", DEFAULT_SINGLE_TX_LIMIT)
    if ctx.amount is None:
        return False
    return ctx.amount > int(limit)


def _client_blocked(ctx: DecisionContext) -> bool:
    if ctx.metadata.get("client_blocked") is True:
        return True
    status = ctx.metadata.get("client_status")
    if not status:
        return False
    return str(status).upper() in BLOCKED_CLIENT_STATUSES


def _period_not_finalized(ctx: DecisionContext) -> bool:
    if ctx.action not in {DecisionAction.PAYOUT_EXPORT, DecisionAction.ACCOUNTING_EXPORT}:
        return False
    status = ctx.metadata.get("billing_period_status")
    if status is None:
        return False
    return str(status).upper() not in FINALIZED_PERIOD_STATUSES


def _document_not_finalized(ctx: DecisionContext) -> bool:
    if ctx.action != DecisionAction.DOCUMENT_FINALIZE:
        return False
    return not bool(ctx.metadata.get("document_acknowledged"))


def _role_based_guard(ctx: DecisionContext) -> bool:
    required_roles = ctx.metadata.get("required_roles")
    if not required_roles:
        return False
    actor_roles = ctx.metadata.get("actor_roles") or []
    required_set = {str(role) for role in required_roles}
    actor_set = {str(role) for role in actor_roles}
    return not bool(required_set & actor_set)


def default_rules() -> list[Rule]:
    return [
        Rule(
            id="MAX_SINGLE_PAYMENT",
            when=_single_transaction_limit,
            outcome=DecisionOutcome.DECLINE,
            explain="amount_exceeds_single_limit",
        ),
        Rule(
            id="CLIENT_BLOCKED",
            when=_client_blocked,
            outcome=DecisionOutcome.DECLINE,
            explain="client_blocked",
        ),
        Rule(
            id="PERIOD_NOT_FINALIZED",
            when=_period_not_finalized,
            outcome=DecisionOutcome.DECLINE,
            explain="billing_period_not_finalized",
        ),
        Rule(
            id="DOCUMENT_NOT_FINALIZED",
            when=_document_not_finalized,
            outcome=DecisionOutcome.DECLINE,
            explain="document_not_acknowledged",
        ),
        Rule(
            id="ROLE_BASED_GUARD",
            when=_role_based_guard,
            outcome=DecisionOutcome.DECLINE,
            explain="missing_required_role",
        ),
    ]


__all__ = [
    "Rule",
    "default_rules",
    "ScoringRule",
    "apply_scoring_rules",
    "default_scoring_rules",
]

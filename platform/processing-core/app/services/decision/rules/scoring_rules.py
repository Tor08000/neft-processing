from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from app.models.risk_score import RiskLevel
from app.services.decision.context import DecisionContext


@dataclass(frozen=True)
class Rule:
    id: str
    when: Callable[[DecisionContext], bool]
    then: RiskLevel
    explain: str


def _blocked_clients_from_env() -> set[str]:
    raw = os.getenv("RISK_BLOCKED_CLIENTS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def default_scoring_rules(*, blocked_clients: Iterable[str] | None = None) -> list[Rule]:
    blocked = set(blocked_clients or _blocked_clients_from_env())

    return [
        Rule(
            id="MAX_SINGLE_PAYMENT_LIMIT",
            when=lambda ctx: ctx.amount is not None and ctx.amount > 10_000_000,
            then=RiskLevel.HIGH,
            explain="amount_exceeds_single_limit",
        ),
        Rule(
            id="CLIENT_BLOCKED",
            when=lambda ctx: ctx.client_id in blocked,
            then=RiskLevel.VERY_HIGH,
            explain="client_is_blocked",
        ),
        Rule(
            id="CLIENT_AGE_LIMIT",
            when=lambda ctx: ctx.age is not None and ctx.age < 18,
            then=RiskLevel.HIGH,
            explain="client_underage",
        ),
    ]


def apply_scoring_rules(ctx: DecisionContext, rules: Sequence[Rule]) -> tuple[RiskLevel, list[str], list[str]]:
    fired: list[Rule] = []
    for rule in rules:
        if rule.when(ctx):
            fired.append(rule)

    if not fired:
        return RiskLevel.LOW, [], []

    fired_sorted = sorted(fired, key=lambda item: item.id)
    explanations = [rule.explain for rule in fired_sorted]
    rule_ids = [rule.id for rule in fired_sorted]
    highest = max((rule.then for rule in fired_sorted), key=_risk_severity)
    return highest, explanations, rule_ids


def _risk_severity(level: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.VERY_HIGH: 3,
    }[level]

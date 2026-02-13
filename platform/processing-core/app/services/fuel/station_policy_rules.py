from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.rule import Rule

_DEFAULT_RULE_NAME = "default_station_risk_red_soft_decline"


@dataclass(frozen=True)
class RuleDecision:
    matched: bool
    policy: str | None = None
    reason_code: str | None = None
    manual_review_required: bool = False


def ensure_default_station_risk_rule(db: Session) -> None:
    rule = (
        db.query(Rule)
        .filter(Rule.scope == "TENANT")
        .filter(Rule.subject_id == "default")
        .filter(Rule.name == _DEFAULT_RULE_NAME)
        .one_or_none()
    )
    payload = {
        "scope": "TENANT",
        "subject_id": "default",
        "name": _DEFAULT_RULE_NAME,
        "selector": {"risk_tags": ["STATION_RISK_RED"]},
        "window": "PER_TXN",
        "metric": "FLAG",
        "policy": "SOFT_DECLINE",
        "meta": {"manual_review": True, "reason_code": "STATION_RISK_RED"},
        "priority": 10,
        "enabled": True,
        "system": True,
    }
    if rule is None:
        db.add(Rule(**payload))
        db.commit()
        return

    changed = False
    for key, value in payload.items():
        if getattr(rule, key) != value:
            setattr(rule, key, value)
            changed = True
    if changed:
        db.commit()


def _selector_matches(selector: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if not selector:
        return True
    for key, expected in selector.items():
        current = context.get(key)
        if key == "risk_tag":
            if expected not in set(context.get("risk_tags") or []):
                return False
            continue
        if key == "risk_tags":
            expected_tags = set(expected or [])
            if not expected_tags.issubset(set(context.get("risk_tags") or [])):
                return False
            continue
        if isinstance(expected, list):
            if current not in expected:
                return False
        elif current != expected:
            return False
    return True


def evaluate_station_policy_rules(db: Session, *, tenant_id: int, risk_tags: list[str]) -> RuleDecision:
    rules = (
        db.query(Rule)
        .filter(Rule.enabled.is_(True))
        .filter(Rule.scope == "TENANT")
        .filter(Rule.subject_id.in_([str(tenant_id), "default"]))
        .order_by(Rule.priority.asc(), Rule.id.asc())
        .all()
    )
    context = {"risk_tags": risk_tags}
    for rule in rules:
        if not _selector_matches(rule.selector or {}, context):
            continue
        meta = rule.meta or {}
        return RuleDecision(
            matched=True,
            policy=rule.policy,
            reason_code=meta.get("reason_code"),
            manual_review_required=bool(meta.get("manual_review")),
        )
    return RuleDecision(matched=False)

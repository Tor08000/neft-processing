from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.audit_log import ActorType, AuditVisibility
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.services.audit_service import AuditService, RequestContext
from app.services.decision.context import DecisionContext
from app.services.decision.explain import build_explain
from app.services.decision.result import DecisionOutcome, DecisionResult
from app.services.decision.rules import Rule, default_rules
from app.services.decision.scoring import RiskScorer, StubRiskScorer
from app.services.decision.versions import DECISION_ENGINE_VERSION


_OUTCOME_SEVERITY = {"DECLINE": 2, "MANUAL_REVIEW": 1, "ALLOW": 0}


class DecisionEngine:
    def __init__(
        self,
        db: Session,
        *,
        rules: list[Rule] | None = None,
        scorer: RiskScorer | None = None,
        threshold: int = 70,
        version: str = DECISION_ENGINE_VERSION,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.rules = rules or default_rules()
        self.scorer = scorer or StubRiskScorer()
        self.threshold = threshold
        self.version = version
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        payload = ctx.to_payload()
        _ensure_json_serializable(payload)
        context_hash = _hash_payload(payload)

        matched_rules: list[str] = []
        rule_explanations: dict[str, str] = {}
        rule_outcome: DecisionOutcome | None = None

        for rule in self.rules:
            if rule.when(ctx):
                matched_rules.append(rule.id)
                rule_explanations[rule.id] = rule.explain
                rule_outcome = _max_outcome(rule_outcome, rule.outcome)

        risk_score = None
        model_version = None
        outcome: DecisionOutcome

        if rule_outcome in {"DECLINE", "MANUAL_REVIEW"}:
            outcome = rule_outcome
        else:
            score = self.scorer.score(ctx)
            risk_score = score.score
            model_version = score.model_version
            outcome = "MANUAL_REVIEW" if risk_score > self.threshold else "ALLOW"

        evaluated_at = self.now_provider()
        explain = build_explain(
            ctx,
            matched_rules=matched_rules,
            rule_explanations=rule_explanations,
            thresholds={"manual_review": self.threshold},
            risk_score=risk_score,
            model_version=model_version,
            evaluated_at=evaluated_at,
        )

        decision_id = new_uuid_str()
        record = DecisionResultRecord(
            id=new_uuid_str(),
            decision_id=decision_id,
            decision_version=self.version,
            action=ctx.action.value,
            outcome=outcome,
            risk_score=risk_score,
            rule_hits=matched_rules,
            model_version=model_version,
            context_hash=context_hash,
            explain=explain,
            created_at=evaluated_at,
        )
        self.db.add(record)
        self.db.flush()

        self._audit_decision(ctx, decision_id, outcome, risk_score, matched_rules, model_version)

        return DecisionResult(
            decision_id=decision_id,
            decision_version=self.version,
            outcome=outcome,
            risk_score=risk_score,
            rule_hits=matched_rules,
            model_version=model_version,
            explain=explain,
        )

    def _audit_decision(
        self,
        ctx: DecisionContext,
        decision_id: str,
        outcome: DecisionOutcome,
        risk_score: int | None,
        rule_hits: list[str],
        model_version: str | None,
    ) -> None:
        event_type = {
            "ALLOW": "DECISION_MADE",
            "DECLINE": "DECISION_DECLINED",
            "MANUAL_REVIEW": "DECISION_MANUAL_REVIEW",
        }[outcome]
        request_ctx = RequestContext(
            actor_type=_map_actor_type(ctx.actor_type),
            actor_id=ctx.metadata.get("actor_id") or ctx.client_id,
            actor_email=ctx.metadata.get("actor_email"),
            actor_roles=ctx.metadata.get("actor_roles"),
            tenant_id=ctx.tenant_id,
        )
        AuditService(self.db).audit(
            event_type=event_type,
            entity_type="decision",
            entity_id=decision_id,
            action="EVALUATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "decision_id": decision_id,
                "action": ctx.action.value,
                "outcome": outcome,
                "score": risk_score,
                "rules": rule_hits,
                "model_version": model_version,
            },
            request_ctx=request_ctx,
        )


def _map_actor_type(actor_type: str) -> ActorType:
    if actor_type in {"CLIENT", "ADMIN"}:
        return ActorType.USER
    return ActorType.SYSTEM


def _hash_payload(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ensure_json_serializable(payload: dict) -> None:
    json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _max_outcome(current: DecisionOutcome | None, new: DecisionOutcome) -> DecisionOutcome:
    if current is None:
        return new
    if _OUTCOME_SEVERITY[new] > _OUTCOME_SEVERITY[current]:
        return new
    return current

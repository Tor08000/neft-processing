from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger
from app.db.types import new_uuid_str
from app.models.audit_log import ActorType, AuditVisibility
from app.models.audit_log import AuditLog
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.risk_decision import RiskDecision
from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionActor, RiskDecisionType, RiskOutcome, RiskSubjectType
from app.services.audit_service import AuditService, RequestContext
from app.services.decision.context import DecisionContext
from app.services.decision.explain import build_explain
from app.services.decision.result import DecisionOutcome, DecisionResult
from app.services.decision.rules import Rule, apply_scoring_rules, default_rules
from app.services.decision.scoring import RiskScorer, StubRiskScorer
from app.services.decision.thresholds import ThresholdEvaluation, evaluate_thresholds
from app.services.decision.versions import DECISION_ENGINE_VERSION
from app.services.risk.policy_resolver import resolve_policy_threshold, resolve_policy_threshold_override
from app.services.risk.training_snapshot import capture_training_snapshot
from app.services.legal_graph import (
    GraphContext,
    LegalGraphBuilder,
    LegalGraphWriteFailure,
    audit_graph_write_failure,
)


logger = get_logger(__name__)


_OUTCOME_SEVERITY = {
    DecisionOutcome.DECLINE: 2,
    DecisionOutcome.MANUAL_REVIEW: 1,
    DecisionOutcome.ALLOW: 0,
}


class DecisionEngine:
    """Deterministic risk decision engine for v4 policies, thresholds, and audits."""

    def __init__(
        self,
        db: Session | None = None,
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
        if now_provider is not None:
            self.now_provider = now_provider
        elif db is None:
            fixed = datetime(2000, 1, 1, tzinfo=timezone.utc)
            self.now_provider = lambda: fixed
        else:
            self.now_provider = lambda: datetime.now(timezone.utc)

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        payload = ctx.to_payload()
        _ensure_json_serializable(payload)
        context_hash = _hash_payload(payload)

        subject_type = _subject_from_action(ctx.action)
        missing_reasons: list[str] = []
        if ctx.amount is None:
            missing_reasons.append("missing_amount")
        if ctx.client_id is None:
            missing_reasons.append("missing_client_id")
        if subject_type is None:
            missing_reasons.append("unknown_action")

        matched_rules: list[str] = []
        rule_explanations: dict[str, str] = {}
        rule_outcome: DecisionOutcome | None = None
        risk_level: RiskLevel | None = None
        reason_codes: list[str] = []
        scoring_rule_ids: list[str] = []
        risk_decision: RiskDecisionType | None = None
        risk_outcome: RiskOutcome | None = None
        threshold_id: str | None = None
        policy_id: str | None = None
        threshold_set_id: str | None = None
        threshold_set = None
        hard_decline = False
        threshold_values: dict[str, int] | None = None

        risk_score = None
        model_version = None
        outcome: DecisionOutcome
        context_blocked = bool(missing_reasons)

        if context_blocked:
            outcome = DecisionOutcome.DECLINE
            risk_score = 100
            risk_level = RiskLevel.VERY_HIGH
            risk_decision = RiskDecisionType.BLOCK
            risk_outcome = RiskOutcome.BLOCK
            threshold_set_id = "context_validation"
            threshold_values = {"block": 0, "review": 0, "allow": 0}
            reason_codes = list(missing_reasons)
            top_reasons = [{"feature": reason, "impact": None} for reason in missing_reasons]
        else:
            for rule in self.rules:
                if rule.when(ctx):
                    matched_rules.append(rule.id)
                    rule_explanations[rule.id] = rule.explain
                    rule_outcome = _max_outcome(rule_outcome, rule.outcome)

            if rule_outcome in {DecisionOutcome.DECLINE, DecisionOutcome.MANUAL_REVIEW}:
                outcome = rule_outcome
                hard_decline = rule_outcome == DecisionOutcome.DECLINE
            else:
                if ctx.scoring_rules:
                    risk_level, reason_codes, scoring_rule_ids = apply_scoring_rules(ctx, ctx.scoring_rules)
                    matched_rules.extend(scoring_rule_ids)
                    for idx, code in enumerate(reason_codes):
                        rule_explanations[scoring_rule_ids[idx]] = code
                    if risk_level in {RiskLevel.HIGH, RiskLevel.VERY_HIGH}:
                        outcome = DecisionOutcome.DECLINE
                        hard_decline = True
                    else:
                        outcome = DecisionOutcome.ALLOW
                else:
                    score = self.scorer.score(ctx)
                    risk_score = score.score
                    model_version = score.model_version
                    outcome = DecisionOutcome.MANUAL_REVIEW if risk_score > self.threshold else DecisionOutcome.ALLOW

        if risk_level:
            risk_score = _score_from_risk_level(risk_level)

        if risk_score is None:
            risk_score = 100 if hard_decline else 0

        evaluated_at = self.now_provider()
        policy_payload: dict | None = None
        decision_payload: dict | None = None
        top_reasons: list[dict] | None = None
        policy_selection = None
        if self.db is not None and not hard_decline and not context_blocked and subject_type is not None:
            policy_override_id = ctx.metadata.get("policy_override_id")
            if policy_override_id:
                policy_selection = resolve_policy_threshold_override(
                    self.db,
                    policy_id=policy_override_id,
                    subject_type=subject_type,
                    score=int(risk_score),
                    now=evaluated_at,
                )
            else:
                policy_selection = resolve_policy_threshold(
                    self.db,
                    subject_type=subject_type,
                    score=int(risk_score),
                    tenant_id=ctx.tenant_id,
                    client_id=ctx.client_id,
                    provider=ctx.metadata.get("provider"),
                    currency=ctx.currency or ctx.metadata.get("currency"),
                    country=ctx.metadata.get("country"),
                    now=evaluated_at,
                )
        if context_blocked:
            decision_payload = {
                "decision": risk_decision.value,
                "risk_level": risk_level.value if risk_level else None,
                "score": int(risk_score),
                "policy": policy_id,
                "model": model_version,
                "top_reasons": top_reasons,
            }
        elif hard_decline:
            risk_decision = RiskDecisionType.BLOCK
            risk_level = risk_level or RiskLevel.VERY_HIGH
            threshold_set_id = threshold_set_id or "hard_rules"
            threshold_values = {"block": 0, "review": 0, "allow": 0}
            risk_outcome = RiskOutcome.BLOCK
            top_reasons = _top_reasons(reason_codes, matched_rules)
            decision_payload = {
                "decision": risk_decision.value,
                "risk_level": risk_level.value if risk_level else None,
                "score": int(risk_score),
                "policy": policy_id,
                "model": model_version,
                "top_reasons": top_reasons,
            }
        elif policy_selection is None and subject_type is not None:
            risk_decision = RiskDecisionType.BLOCK
            risk_level = risk_level or RiskLevel.VERY_HIGH
            threshold_set_id = "missing_thresholds"
            threshold_values = {"block": 0, "review": 0, "allow": 0}
            risk_outcome = RiskOutcome.BLOCK
            reason_codes = ["missing_threshold_set"]
            top_reasons = [{"feature": "missing_threshold_set", "impact": None}]
            decision_payload = {
                "decision": risk_decision.value,
                "risk_level": risk_level.value if risk_level else None,
                "score": int(risk_score),
                "policy": policy_id,
                "model": model_version,
                "top_reasons": top_reasons,
                "reason": "missing_threshold_set",
            }
        elif policy_selection is not None:
            policy = policy_selection.policy
            threshold_set = policy_selection.threshold_set
            threshold = policy_selection.threshold
            policy_id = policy.id if policy else None
            threshold_id = str(threshold.id) if threshold is not None else None
            threshold_set_id = threshold_set.id
            thresholds_override = ctx.metadata.get("thresholds_override")
            if threshold is None and threshold_set.block_threshold is not None:
                if thresholds_override:
                    evaluation = _evaluate_threshold_override(int(risk_score), thresholds_override)
                else:
                    evaluation = evaluate_thresholds(int(risk_score), threshold_set)
                threshold_values = evaluation.thresholds
                risk_outcome = evaluation.outcome
                risk_decision = evaluation.decision
                outcome = _max_outcome(outcome, _outcome_from_risk_outcome(risk_outcome))
                risk_level = _risk_level_from_score(int(risk_score))
            elif threshold is not None:
                risk_decision = _decision_from_threshold(threshold)
                risk_level = threshold.risk_level
                outcome = _max_outcome(outcome, _outcome_from_decision(risk_decision))
            policy_payload = {
                "policy_id": policy_id,
                "threshold_id": threshold_id,
                "threshold_set_id": threshold_set_id,
            }
            decision_payload = {
                "decision": risk_decision.value,
                "risk_level": risk_level.value if risk_level else None,
                "score": int(risk_score),
                "policy": policy_id,
                "model": model_version,
            }
            if risk_decision in {RiskDecisionType.BLOCK, RiskDecisionType.ESCALATE}:
                top_reasons = _top_reasons(reason_codes, matched_rules)
                decision_payload["top_reasons"] = top_reasons
        elif risk_decision is None:
            risk_decision = _decision_from_outcome(outcome)
            threshold_id = "legacy"
            threshold_set_id = "legacy"
            threshold_values = {"block": self.threshold, "review": self.threshold, "allow": 0}
            if outcome == DecisionOutcome.ALLOW:
                risk_outcome = RiskOutcome.ALLOW
            elif outcome == DecisionOutcome.MANUAL_REVIEW:
                risk_outcome = RiskOutcome.REVIEW_REQUIRED
            else:
                risk_outcome = RiskOutcome.BLOCK

        if risk_level is None:
            risk_level = _risk_level_from_score(int(risk_score))

        if risk_outcome is None:
            risk_outcome = _risk_outcome_from_decision(risk_decision, outcome)

        factors = _explain_factors(reason_codes, matched_rules, rule_explanations)
        model_name = None
        if policy_selection and policy_selection.policy:
            model_name = policy_selection.policy.model_selector
        model_name = model_name or ctx.metadata.get("model_name")
        explain = build_explain(
            ctx,
            matched_rules=matched_rules,
            rule_explanations=rule_explanations,
            thresholds=threshold_values or {"block": self.threshold, "review": self.threshold, "allow": 0},
            risk_score=risk_score,
            decision=risk_outcome.value if risk_outcome else None,
            model_version=model_version,
            model_name=model_name,
            policy_label=policy_id,
            factors=factors,
            evaluated_at=evaluated_at,
            policy=policy_payload,
            decision_payload=decision_payload,
            top_reasons=top_reasons,
        )
        if reason_codes:
            explain["reason_codes"] = reason_codes
            explain["rules_fired"] = scoring_rule_ids

        decision_id = new_uuid_str()
        if self.db is not None:
            record = DecisionResultRecord(
                id=new_uuid_str(),
                decision_id=decision_id,
                decision_version=self.version,
                action=ctx.action.value if hasattr(ctx.action, "value") else ctx.action,
                outcome=outcome.value,
                risk_score=risk_score,
                rule_hits=matched_rules,
                model_version=model_version,
                context_hash=context_hash,
                explain=explain,
                created_at=evaluated_at,
            )
            self.db.add(record)
            self.db.flush()

            audit_record = self._audit_decision(
                ctx, decision_id, outcome, risk_score, matched_rules, model_version
            )
            subject_type = _subject_from_action(ctx.action)
            subject_id = _subject_id_from_context(ctx)
            if subject_type is not None and audit_record is not None:
                risk_decision_record = RiskDecision(
                    id=new_uuid_str(),
                    decision_id=decision_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    score=int(risk_score),
                    risk_level=risk_level,
                    threshold_set_id=threshold_set_id or "legacy",
                    policy_id=policy_id,
                    outcome=risk_decision or _decision_from_outcome(outcome),
                    model_version=model_version,
                    reasons=top_reasons or _top_reasons(reason_codes, matched_rules),
                    features_snapshot=ctx.to_payload(),
                    decided_at=evaluated_at,
                    decided_by=_decision_actor(ctx.actor_type),
                    audit_id=audit_record.id,
                )
            self.db.add(risk_decision_record)
            self.db.flush()
            self._audit_risk_decision(
                ctx,
                decision_id=decision_id,
                risk_decision=risk_decision_record,
            )
            try:
                graph_context = GraphContext(
                    tenant_id=ctx.tenant_id or 0,
                    request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id=ctx.actor_id),
                )
                LegalGraphBuilder(self.db, context=graph_context).ensure_risk_decision_graph(risk_decision_record)
            except Exception as exc:  # noqa: BLE001 - graph must not block decisions
                logger.warning(
                    "legal_graph_risk_decision_failed",
                    extra={"decision_id": decision_id, "error": str(exc)},
                )
                audit_graph_write_failure(
                    self.db,
                    failure=LegalGraphWriteFailure(
                        entity_type="risk_decision",
                        entity_id=str(risk_decision_record.id),
                        error=str(exc),
                    ),
                    request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id=ctx.actor_id),
                )
            capture_training_snapshot(
                self.db,
                ctx,
                decision_id=decision_id,
                score=int(risk_score),
                outcome=risk_outcome or RiskOutcome.ALLOW,
                model_version=model_version,
                threshold_set=threshold_set if policy_selection else None,
                policy=policy_selection.policy if policy_selection else None,
                evaluated_at=evaluated_at,
            )

        return DecisionResult(
            decision_id=decision_id,
            decision_version=self.version,
            outcome=outcome,
            risk_score=risk_score,
            risk_level=risk_level,
            rule_hits=matched_rules,
            model_version=model_version,
            explain=explain,
            risk_decision=risk_decision,
            threshold_set_id=threshold_set_id,
            policy_id=policy_id,
        )

    def _audit_decision(
        self,
        ctx: DecisionContext,
        decision_id: str,
        outcome: DecisionOutcome,
        risk_score: int | None,
        rule_hits: list[str],
        model_version: str | None,
    ) -> AuditLog | None:
        event_type = {
            DecisionOutcome.ALLOW: "DECISION_MADE",
            DecisionOutcome.DECLINE: "DECISION_DECLINED",
            DecisionOutcome.MANUAL_REVIEW: "DECISION_MANUAL_REVIEW",
        }[outcome]
        request_ctx = RequestContext(
            actor_type=_map_actor_type(ctx.actor_type),
            actor_id=ctx.metadata.get("actor_id") or ctx.client_id,
            actor_email=ctx.metadata.get("actor_email"),
            actor_roles=ctx.metadata.get("actor_roles"),
            tenant_id=ctx.tenant_id,
        )
        return AuditService(self.db).audit(
            event_type=event_type,
            entity_type="decision",
            entity_id=decision_id,
            action="EVALUATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "decision_id": decision_id,
                "action": ctx.action.value if hasattr(ctx.action, "value") else ctx.action,
                "outcome": outcome.value,
                "score": risk_score,
                "rules": rule_hits,
                "model_version": model_version,
            },
            request_ctx=request_ctx,
        )

    def _audit_risk_decision(
        self,
        ctx: DecisionContext,
        *,
        decision_id: str,
        risk_decision: RiskDecision,
    ) -> None:
        event_type = "RISK_DECISION_MADE"
        if risk_decision.outcome == RiskDecisionType.BLOCK:
            event_type = "RISK_DECISION_BLOCKED"
        elif risk_decision.outcome == RiskDecisionType.ESCALATE:
            event_type = "RISK_DECISION_ESCALATED"

        request_ctx = RequestContext(
            actor_type=_map_actor_type(ctx.actor_type),
            actor_id=ctx.metadata.get("actor_id") or ctx.client_id,
            actor_email=ctx.metadata.get("actor_email"),
            actor_roles=ctx.metadata.get("actor_roles"),
            tenant_id=ctx.tenant_id,
        )
        AuditService(self.db).audit(
            event_type=event_type,
            entity_type="risk_decision",
            entity_id=risk_decision.id,
            action="EVALUATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "decision_id": decision_id,
                "subject_type": risk_decision.subject_type.value,
                "subject_id": risk_decision.subject_id,
                "score": risk_decision.score,
                "risk_level": risk_decision.risk_level.value,
                "outcome": risk_decision.outcome.value,
                "threshold_set_id": risk_decision.threshold_set_id,
                "policy_id": risk_decision.policy_id,
                "model_version": risk_decision.model_version,
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


def _evaluate_threshold_override(score: int, override: dict) -> ThresholdEvaluation:
    thresholds = {
        "block": int(override.get("block", 100)),
        "review": int(override.get("review", 80)),
        "allow": int(override.get("allow", 0)),
    }
    if score >= thresholds["block"]:
        outcome = RiskOutcome.BLOCK
        decision = RiskDecisionType.BLOCK
    elif score >= thresholds["review"]:
        outcome = RiskOutcome.REVIEW_REQUIRED
        decision = RiskDecisionType.ALLOW_WITH_REVIEW
    elif score >= thresholds["allow"]:
        outcome = RiskOutcome.ALLOW
        decision = RiskDecisionType.ALLOW
    else:
        outcome = RiskOutcome.ALLOW_WITH_LOG
        decision = RiskDecisionType.ALLOW
    return ThresholdEvaluation(outcome=outcome, decision=decision, thresholds=thresholds)


def _ensure_json_serializable(payload: dict) -> None:
    json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _max_outcome(current: DecisionOutcome | None, new: DecisionOutcome) -> DecisionOutcome:
    if current is None:
        return new
    if _OUTCOME_SEVERITY[new] > _OUTCOME_SEVERITY[current]:
        return new
    return current


def _score_from_risk_level(level: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 10,
        RiskLevel.MEDIUM: 40,
        RiskLevel.HIGH: 80,
        RiskLevel.VERY_HIGH: 95,
    }[level]


def _risk_level_from_score(score: int) -> RiskLevel:
    if score <= 30:
        return RiskLevel.LOW
    if score <= 60:
        return RiskLevel.MEDIUM
    if score <= 80:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH


def _decision_from_threshold(threshold) -> RiskDecisionType:
    if threshold.outcome == RiskDecisionType.ALLOW and threshold.requires_manual_review:
        return RiskDecisionType.ALLOW_WITH_REVIEW
    return RiskDecisionType(threshold.outcome)


def _decision_from_outcome(outcome: DecisionOutcome) -> RiskDecisionType:
    if outcome == DecisionOutcome.ALLOW:
        return RiskDecisionType.ALLOW
    if outcome == DecisionOutcome.MANUAL_REVIEW:
        return RiskDecisionType.ESCALATE
    return RiskDecisionType.BLOCK


def _outcome_from_decision(decision: RiskDecisionType) -> DecisionOutcome:
    if decision == RiskDecisionType.BLOCK:
        return DecisionOutcome.DECLINE
    if decision == RiskDecisionType.ESCALATE:
        return DecisionOutcome.MANUAL_REVIEW
    return DecisionOutcome.ALLOW


def _outcome_from_risk_outcome(outcome: RiskOutcome) -> DecisionOutcome:
    if outcome == RiskOutcome.BLOCK:
        return DecisionOutcome.DECLINE
    if outcome == RiskOutcome.REVIEW_REQUIRED:
        return DecisionOutcome.MANUAL_REVIEW
    return DecisionOutcome.ALLOW


def _risk_outcome_from_decision(
    decision: RiskDecisionType | None, outcome: DecisionOutcome
) -> RiskOutcome:
    if decision == RiskDecisionType.BLOCK:
        return RiskOutcome.BLOCK
    if decision in {RiskDecisionType.ALLOW_WITH_REVIEW, RiskDecisionType.ESCALATE}:
        return RiskOutcome.REVIEW_REQUIRED
    if outcome == DecisionOutcome.MANUAL_REVIEW:
        return RiskOutcome.REVIEW_REQUIRED
    return RiskOutcome.ALLOW


def _top_reasons(reason_codes: list[str], matched_rules: list[str]) -> list[dict]:
    if reason_codes:
        return [{"feature": code, "impact": None} for code in reason_codes[:3]]
    return [{"feature": rule_id, "impact": None} for rule_id in matched_rules[:3]]


def _explain_factors(
    reason_codes: list[str],
    matched_rules: list[str],
    rule_explanations: dict[str, str],
) -> list[str]:
    if reason_codes:
        return reason_codes[:3]
    if rule_explanations:
        ordered = [rule_explanations[rule_id] for rule_id in matched_rules if rule_id in rule_explanations]
        return ordered[:3] or matched_rules[:3]
    return matched_rules[:3]


def _subject_from_action(action) -> RiskSubjectType | None:
    value = action.value if hasattr(action, "value") else str(action)
    normalized = value.upper()
    if "PAYMENT" in normalized:
        return RiskSubjectType.PAYMENT
    if "INVOICE" in normalized or "CREDIT_NOTE" in normalized:
        return RiskSubjectType.INVOICE
    if "PAYOUT" in normalized:
        return RiskSubjectType.PAYOUT
    if "DOCUMENT" in normalized:
        return RiskSubjectType.DOCUMENT
    if "EXPORT" in normalized:
        return RiskSubjectType.EXPORT
    return None


def _subject_id_from_context(ctx: DecisionContext) -> str:
    return (
        ctx.metadata.get("subject_id")
        or ctx.metadata.get("operation_id")
        or ctx.metadata.get("invoice_id")
        or ctx.invoice_id
        or ctx.billing_period_id
        or ctx.client_id
        or "unknown"
    )


def _decision_actor(actor_type: str) -> RiskDecisionActor:
    if actor_type == "ADMIN":
        return RiskDecisionActor.ADMIN
    return RiskDecisionActor.SYSTEM

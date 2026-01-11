from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from app.deps.db import get_db
from app.models.operation import Operation
from app.models.unified_rule import RuleSetVersion, UnifiedRule, UnifiedRulePolicy
from app.schemas.unified_rules import (
    RuleEvaluationContext,
    RuleEvaluationObject,
    RuleEvaluationSubject,
    SandboxRequest,
    SandboxResponse,
    SandboxVersionInfo,
)
from app.services.unified_rules_engine import (
    OperationsMetricsProvider,
    SyntheticMetricsProvider,
    evaluate_rules,
    get_active_version,
    resolve_decision,
)

router = APIRouter(prefix='/rules', tags=['rules'])

class SimIn(BaseModel):
    tenant_id: int = 1
    card_token: str
    qty: float = 0

@router.post('/simulate')
def simulate(b: SimIn, db: Session = Depends(get_db)):
    rule = db.execute(text("SELECT value,policy FROM rules WHERE scope='CARD' AND subject_id=:t AND enabled=true AND metric='LITERS' ORDER BY priority ASC LIMIT 1"), {'t': b.card_token}).first()
    if not rule:
        return {'decision': 'ALLOW', 'limit': None, 'used': 0, 'remain': None}
    value, policy = float(rule[0]), rule[1]
    used = db.execute(text("SELECT COALESCE(SUM(qty),0) FROM transactions t JOIN cards c ON c.id=t.card_id WHERE c.token=:t AND t.auth_ts>=date_trunc('day',now()) AND t.state IN ('PRE_AUTH','CAPTURED','SETTLED')"), {'t': b.card_token}).scalar() or 0.0
    remain = max(0.0, value - float(used))
    decision = 'ALLOW' if b.qty <= remain else ('DECLINE' if policy.startswith('HARD') else 'SOFT_DECLINE')
    return {'decision': decision, 'limit': value, 'used': float(used), 'remain': remain}


@router.post('/sandbox:evaluate', response_model=SandboxResponse)
def sandbox_evaluate(payload: SandboxRequest, db: Session = Depends(get_db)) -> SandboxResponse:
    if payload.mode == "synthetic":
        context_payload = payload.context
        context = RuleEvaluationContext(
            timestamp=payload.at,
            scope=payload.scope,
            subject=RuleEvaluationSubject(
                client_id=context_payload.get("client_id"),
                partner_id=context_payload.get("partner_id"),
                user_id=context_payload.get("user_id"),
            ),
            object=RuleEvaluationObject(
                card_id=context_payload.get("card_id"),
                vehicle_id=context_payload.get("vehicle_id"),
                endpoint=context_payload.get("endpoint"),
                ip=context_payload.get("ip"),
                country=context_payload.get("country"),
                amount=context_payload.get("amount"),
                currency=context_payload.get("currency"),
                method=context_payload.get("method"),
                document_id=context_payload.get("document_id"),
            ),
        )
        metrics_provider = SyntheticMetricsProvider(payload.synthetic_metrics)
        version_id = payload.version_id
    else:
        operation = (
            db.query(Operation)
            .filter(Operation.operation_id == payload.transaction_id)
            .one_or_none()
        )
        if operation is None:
            raise HTTPException(status_code=404, detail="transaction_not_found")
        context = RuleEvaluationContext(
            timestamp=operation.created_at,
            scope=payload.scope,
            subject=RuleEvaluationSubject(client_id=operation.client_id),
            object=RuleEvaluationObject(
                card_id=operation.card_id,
                amount=operation.amount,
                currency=operation.currency,
            ),
        )
        metrics_provider = OperationsMetricsProvider(db)
        version_id = payload.version_id

    version = (
        db.query(RuleSetVersion).filter(RuleSetVersion.id == version_id).one_or_none()
        if version_id
        else get_active_version(db, context.scope)
    )
    if version is None:
        return SandboxResponse(
            version=None,
            matched_rules=[],
            decision=UnifiedRulePolicy.ALLOW,
            reason_codes=[],
            explain={
                "inputs": context.model_dump(),
                "metrics": payload.synthetic_metrics if payload.mode == "synthetic" else {},
                "resolution": {"decision": UnifiedRulePolicy.ALLOW.value},
            },
        )

    rules = (
        db.query(UnifiedRule)
        .filter(UnifiedRule.version_id == version.id)
        .order_by(UnifiedRule.priority.desc(), UnifiedRule.id.asc())
        .all()
    )
    matched = evaluate_rules(rules, context, metrics_provider)
    decision, ordered = resolve_decision(matched)
    matched_rules = [
        {
            "code": item.rule.code,
            "policy": item.rule.policy,
            "priority": item.rule.priority,
            "reason_code": item.rule.reason_code,
            "explain": item.explain,
        }
        for item in ordered
    ]
    reason_codes = [item.rule.reason_code for item in ordered if item.rule.reason_code]
    metrics_payload = payload.synthetic_metrics if payload.mode == "synthetic" else {}
    return SandboxResponse(
        version=SandboxVersionInfo(rule_set_version_id=version.id, scope=version.scope),
        matched_rules=matched_rules,
        decision=decision,
        reason_codes=reason_codes,
        explain={
            "inputs": context.model_dump(),
            "metrics": metrics_payload,
            "resolution": {
                "decision": decision.value,
                "matched_order": [item.rule.code for item in ordered],
            },
        },
    )

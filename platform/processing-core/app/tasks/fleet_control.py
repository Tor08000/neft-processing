from __future__ import annotations

from datetime import datetime, timedelta, timezone

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.fleet_intelligence_actions import FISuggestedAction, FISuggestedActionStatus
from app.services.audit_service import AuditService, RequestContext
from app.models.audit_log import ActorType
from app.services.explain import snapshot as explain_snapshot
from app.services.fleet_intelligence.control import effects, explain, insights, policies, repository
from app.services.ops import escalations as ops_escalations
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.services.ops.reason_codes import OpsReasonCode

logger = get_logger(__name__)


@celery_client.task(name="fleet_control.nightly")
def fleet_control_nightly_task(day_offset: int = 1) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        target_day = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
        new_insights = insights.generate_insights_for_day(session, day=target_day)
        suggested_count = 0
        for insight in new_insights:
            for action in policies.suggest_actions_for_insight(insight):
                repository.upsert_suggested_action(session, action=action)
                _audit_action_proposed(session, action)
                suggested_count += 1
        effects_count = len(effects.measure_action_effects(session, as_of=datetime.now(timezone.utc)))
        expired_count = _scan_for_sla_expired(session)
        session.commit()
        return {
            "day": int(target_day.strftime("%Y%m%d")),
            "insights": len(new_insights),
            "suggested": suggested_count,
            "effects": effects_count,
            "sla_escalations": expired_count,
        }
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fleet_control.nightly_failed")
        raise
    finally:
        session.close()


def _audit_action_proposed(db, action: FISuggestedAction) -> None:
    audit = AuditService(db)
    audit.audit(
        event_type="FI_ACTION_PROPOSED",
        entity_type="fi_suggested_action",
        entity_id=str(action.id),
        action="CREATE",
        after={
            "action_id": str(action.id),
            "action_code": action.action_code.value,
            "insight_id": str(action.insight_id),
            "target_system": action.target_system.value,
            "status": action.status.value,
        },
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM),
    )


def _scan_for_sla_expired(db) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    actions = (
        db.query(FISuggestedAction)
        .filter(FISuggestedAction.status == FISuggestedActionStatus.APPROVED)
        .filter(FISuggestedAction.approved_at <= cutoff)
        .all()
    )
    escalations = 0
    for action in actions:
        insight = repository.get_insight(db, insight_id=str(action.insight_id))
        if not insight:
            continue
        snapshot_payload = explain.build_fleet_control_snapshot(db, insight_id=str(insight.id))
        if not snapshot_payload:
            continue
        persisted = explain_snapshot.persist_snapshot(
            db,
            tenant_id=insight.tenant_id,
            subject_type="fi_insight",
            subject_id=str(insight.id),
            payload=snapshot_payload,
        )
        target = _map_target(action)
        reason_code = _map_reason_code(target)
        ops_escalations.create_escalation_if_missing(
            db,
            tenant_id=insight.tenant_id,
            target=target,
            priority=OpsEscalationPriority.MEDIUM,
            primary_reason=insight.primary_reason,
            subject_type="fi_insight",
            subject_id=str(insight.id),
            source=OpsEscalationSource.AUTO_SLA_EXPIRED,
            client_id=insight.client_id,
            reason_code=reason_code.value,
            unified_explain_snapshot_hash=persisted.snapshot.snapshot_hash,
            unified_explain_snapshot=persisted.snapshot.snapshot_json,
            meta={
                "action_id": str(action.id),
                "action_code": action.action_code.value,
                "status": action.status.value,
            },
        )
        escalations += 1
    return escalations


def _map_target(action: FISuggestedAction) -> OpsEscalationTarget:
    if action.target_system.value == "CRM":
        return OpsEscalationTarget.CRM
    if action.target_system.value == "LOGISTICS":
        return OpsEscalationTarget.LOGISTICS
    return OpsEscalationTarget.CRM


def _map_reason_code(target: OpsEscalationTarget) -> OpsReasonCode:
    if target == OpsEscalationTarget.LOGISTICS:
        return OpsReasonCode.LOGISTICS_DEVIATION
    if target == OpsEscalationTarget.COMPLIANCE:
        return OpsReasonCode.RISK_BLOCK
    if target == OpsEscalationTarget.FINANCE:
        return OpsReasonCode.MONEY_INVARIANT_VIOLATION
    return OpsReasonCode.FEATURE_DISABLED


__all__ = ["fleet_control_nightly_task"]

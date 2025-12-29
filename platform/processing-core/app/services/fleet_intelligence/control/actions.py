from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.crm import CRMFeatureFlagType
from app.models.fleet_intelligence_actions import (
    FAppliedActionStatus,
    FIAppliedAction,
    FIInsightStatus,
    FISuggestedAction,
    FISuggestedActionStatus,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.crm import repository as crm_repository
from app.services.crm import settings as crm_settings
from app.services.crm import sync as crm_sync
from app.services.explain import snapshot as explain_snapshot
from app.services.fleet_intelligence.control import effects, explain, repository
from app.services.ops import escalations as ops_escalations
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.services.ops.reason_codes import OpsReasonCode


def approve_suggested_action(
    db: Session,
    *,
    action: FISuggestedAction,
    reason_code: str,
    reason_text: str | None,
    actor: str | None,
) -> FISuggestedAction:
    _require_reason(reason_code)
    if action.status not in {FISuggestedActionStatus.PROPOSED}:
        raise ValueError("invalid_action_status")
    action.status = FISuggestedActionStatus.APPROVED
    action.approved_at = datetime.now(timezone.utc)
    action.approved_by = actor
    action.approve_reason = reason_text
    insight = repository.get_insight(db, insight_id=str(action.insight_id))
    if insight and insight.status in {FIInsightStatus.OPEN, FIInsightStatus.ACKED}:
        insight.status = FIInsightStatus.ACTION_PLANNED
    _audit_action(db, event_type="FI_ACTION_APPROVED", action=action, reason=reason_text)
    return action


def apply_suggested_action(
    db: Session,
    *,
    action: FISuggestedAction,
    reason_code: str,
    reason_text: str | None,
    actor: str | None,
) -> FIAppliedAction:
    _require_reason(reason_code)
    if action.status != FISuggestedActionStatus.APPROVED:
        raise ValueError("action_not_approved")
    insight = repository.get_insight(db, insight_id=str(action.insight_id))
    if not insight:
        raise ValueError("insight_not_found")

    before_state = effects.build_before_state(db, insight=insight, as_of=datetime.now(timezone.utc))
    applied = FIAppliedAction(
        insight_id=insight.id,
        action_code=action.action_code,
        applied_by=actor,
        reason_code=reason_code.strip().upper(),
        reason_text=reason_text.strip() if reason_text and reason_text.strip() else None,
        before_state=before_state,
        status=FAppliedActionStatus.SUCCESS,
    )
    try:
        _apply_to_target(db, action=action, insight=insight, actor=actor)
        action.status = FISuggestedActionStatus.APPLIED
        insight.status = FIInsightStatus.MONITORING
        repository.add_applied_action(db, applied)
        _audit_action(db, event_type="FI_ACTION_APPLIED", action=action, reason=reason_text, applied=applied)
    except Exception as exc:  # noqa: BLE001
        applied.status = FAppliedActionStatus.FAILED
        applied.error_message = str(exc)
        repository.add_applied_action(db, applied)
        _audit_action(db, event_type="FI_ACTION_FAILED", action=action, reason=str(exc), applied=applied)
        _create_ops_escalation(db, insight=insight, action=action, reason=str(exc))
    return applied


def _apply_to_target(db: Session, *, action: FISuggestedAction, insight, actor: str | None) -> None:
    payload = action.payload or {}
    if action.target_system.value == "CRM":
        if "limit_profile_id" in payload:
            _apply_limit_profile(db, client_id=insight.client_id, profile_id=payload["limit_profile_id"], actor=actor)
            return
        if "feature_flag" in payload:
            feature = CRMFeatureFlagType(payload["feature_flag"])
            enabled = bool(payload.get("enabled", True))
            crm_settings.set_feature_flag(
                db,
                tenant_id=insight.tenant_id,
                client_id=insight.client_id,
                feature=feature,
                enabled=enabled,
                updated_by=actor,
            )
            return
        raise ValueError("crm_payload_missing")
    if action.target_system.value == "LOGISTICS":
        raise ValueError("logistics_apply_not_implemented")
    raise ValueError("action_target_not_supported")


def _apply_limit_profile(db: Session, *, client_id: str, profile_id: str, actor: str | None) -> None:
    contract = crm_repository.get_active_contract(db, client_id=client_id)
    if not contract:
        raise ValueError("crm_contract_not_found")
    contract.limit_profile_id = profile_id
    crm_repository.update_contract(db, contract)
    crm_sync.apply_contract(db, contract=contract, request_ctx=RequestContext(actor_type=ActorType.USER, actor_id=actor))


def _create_ops_escalation(db: Session, *, insight, action: FISuggestedAction, reason: str) -> None:
    snapshot_payload = explain.build_fleet_control_snapshot(db, insight_id=str(insight.id))
    if not snapshot_payload:
        return
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
        source=OpsEscalationSource.SYSTEM,
        client_id=insight.client_id,
        reason_code=reason_code.value,
        unified_explain_snapshot_hash=persisted.snapshot.snapshot_hash,
        unified_explain_snapshot=persisted.snapshot.snapshot_json,
        meta={
            "action_id": str(action.id),
            "action_code": action.action_code.value,
            "error": reason,
        },
    )


def _require_reason(reason_code: str) -> None:
    if not reason_code or not reason_code.strip():
        raise ValueError("reason_code_required")


def _audit_action(
    db: Session,
    *,
    event_type: str,
    action: FISuggestedAction,
    reason: str | None,
    applied: FIAppliedAction | None = None,
) -> None:
    audit = AuditService(db)
    insight = repository.get_insight(db, insight_id=str(action.insight_id))
    payload: dict[str, Any] = {
        "action_id": str(action.id),
        "action_code": action.action_code.value,
        "status": action.status.value,
        "target_system": action.target_system.value,
        "reason": reason,
    }
    if insight:
        payload["insight_id"] = str(insight.id)
    if applied:
        payload["applied_action_id"] = str(applied.id)
        payload["applied_status"] = applied.status.value
        payload["error_message"] = applied.error_message
    audit.audit(
        event_type=event_type,
        entity_type="fi_suggested_action",
        entity_id=str(action.id),
        action="UPDATE",
        after=payload,
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=insight.tenant_id if insight else None),
    )


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


__all__ = ["approve_suggested_action", "apply_suggested_action"]

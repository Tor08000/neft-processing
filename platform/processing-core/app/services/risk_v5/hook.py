from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import event

from neft_shared.logging_setup import get_logger

from app.services.risk_v5.config import get_risk_v5_config

logger = get_logger(__name__)
_REGISTERED = False

if TYPE_CHECKING:
    from app.models.risk_decision import RiskDecision


def register_shadow_hook() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    try:
        from app.models.risk_decision import RiskDecision

        event.listen(RiskDecision, "after_insert", _on_risk_decision_insert)
        _REGISTERED = True
    except Exception as exc:  # noqa: BLE001 - never block core
        logger.warning("risk_v5_shadow_hook_register_failed", extra={"error": str(exc)})


def _on_risk_decision_insert(mapper, connection, target: RiskDecision) -> None:
    config = get_risk_v5_config()
    if not config.shadow_enabled:
        return

    try:
        from app.db import SessionLocal
        from app.services.audit_service import AuditService, RequestContext
        from app.services.risk_v5.labels import persist_label, resolve_label
        from app.services.risk_v5.metrics import metrics
        from app.services.risk_v5.shadow import enqueue_shadow_decision
    except Exception as exc:  # noqa: BLE001 - must not impact v4/core
        logger.warning("risk_v5_shadow_import_failed", extra={"error": str(exc)})
        return

    session = SessionLocal()
    try:
        with session.begin():
            shadow = enqueue_shadow_decision(session, target)
            if shadow:
                label = resolve_label(
                    session,
                    decision_id=shadow.decision_id,
                    subject_type=shadow.subject_type,
                    subject_id=shadow.subject_id,
                )
                metrics.observe_label(available=label is not None)
                if label:
                    persist_label(
                        session,
                        decision_id=shadow.decision_id,
                        subject_type=shadow.subject_type,
                        subject_id=shadow.subject_id,
                        label=label,
                    )
    except Exception:  # noqa: BLE001 - shadow must never impact v4
        logger.exception("risk_v5_shadow_hook_failed", extra={"decision_id": target.decision_id})
        try:
            AuditService(session).audit(
                event_type="RISK_V5_SHADOW_FAILED",
                entity_type="risk_decision",
                entity_id=str(getattr(target, "decision_id", "")),
                action="SHADOW",
                request_ctx=RequestContext(actor_type="SYSTEM"),
                after={"decision_id": str(getattr(target, "decision_id", ""))},
                reason="risk_v5_shadow_hook_failed",
            )
        except Exception:  # noqa: BLE001
            logger.warning("risk_v5_shadow_audit_failed", extra={"decision_id": target.decision_id})
    finally:
        session.close()


__all__ = ["register_shadow_hook"]

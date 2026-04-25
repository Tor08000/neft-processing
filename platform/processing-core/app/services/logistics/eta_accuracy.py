from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsETAAccuracy,
    LogisticsETAMethod,
    LogisticsOrder,
    LogisticsRiskSignal,
    LogisticsRiskSignalType,
)
from app.services.audit_service import RequestContext
from app.services.logistics import events, repository
from app.services.logistics.defaults import ETA_ACCURACY_DEFAULTS, RISK_SIGNAL_DEFAULTS
from app.services.logistics.metrics import metrics as logistics_metrics
from app.services.logistics.utils import ensure_aware


def record_snapshot(
    db: Session,
    *,
    order: LogisticsOrder,
    computed_at: datetime,
    eta_end_at: datetime,
    method,
    confidence: int,
    request_ctx: RequestContext | None = None,
) -> LogisticsETAAccuracy:
    accuracy = LogisticsETAAccuracy(
        order_id=str(order.id),
        computed_at=ensure_aware(computed_at),
        eta_end_at=ensure_aware(eta_end_at),
        actual_end_at=ensure_aware(order.actual_end_at),
        error_minutes=None,
        method=method,
        confidence=confidence,
    )
    db.add(accuracy)
    db.flush()
    accuracy_id = str(accuracy.id)
    db.commit()
    accuracy = repository.refresh_by_id(db, accuracy, LogisticsETAAccuracy, accuracy_id)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ETA_ERROR_COMPUTED,
        entity_type="logistics_eta_accuracy",
        entity_id=str(accuracy.id),
        payload={"order_id": str(order.id), "method": method.value, "confidence": confidence},
        request_ctx=request_ctx,
    )
    return accuracy


def record_completion(
    db: Session,
    *,
    order: LogisticsOrder,
    request_ctx: RequestContext | None = None,
) -> LogisticsETAAccuracy | None:
    snapshots = repository.list_eta_snapshots(db, order_id=str(order.id), limit=5)
    latest = None
    for snapshot in snapshots:
        if (
            snapshot.method == LogisticsETAMethod.LAST_KNOWN
            and ensure_aware(snapshot.eta_end_at) == ensure_aware(order.actual_end_at)
        ):
            continue
        latest = snapshot
        break
    if not latest or order.actual_end_at is None:
        return None

    computed_at = ensure_aware(latest.computed_at)
    eta_end_at = ensure_aware(latest.eta_end_at)
    actual_end_at = ensure_aware(order.actual_end_at)
    error_minutes = int(abs((actual_end_at - eta_end_at).total_seconds() / 60)) if actual_end_at else None

    accuracy = LogisticsETAAccuracy(
        order_id=str(order.id),
        computed_at=computed_at,
        eta_end_at=eta_end_at,
        actual_end_at=actual_end_at,
        error_minutes=error_minutes,
        method=latest.method,
        confidence=latest.eta_confidence,
    )
    db.add(accuracy)
    db.flush()
    accuracy_id = str(accuracy.id)
    db.commit()
    accuracy = repository.refresh_by_id(db, accuracy, LogisticsETAAccuracy, accuracy_id)

    events.audit_event(
        db,
        event_type=events.LOGISTICS_ETA_ERROR_COMPUTED,
        entity_type="logistics_eta_accuracy",
        entity_id=str(accuracy.id),
        payload={
            "order_id": str(order.id),
            "error_minutes": error_minutes,
            "eta_end_at": eta_end_at,
            "actual_end_at": actual_end_at,
        },
        request_ctx=request_ctx,
    )
    if error_minutes is not None and error_minutes >= ETA_ACCURACY_DEFAULTS.eta_error_medium_minutes:
        severity = (
            RISK_SIGNAL_DEFAULTS.eta_anomaly_severity
            if error_minutes >= ETA_ACCURACY_DEFAULTS.eta_error_high_minutes
            else RISK_SIGNAL_DEFAULTS.eta_anomaly_medium_severity
        )
        signal = LogisticsRiskSignal(
            tenant_id=order.tenant_id,
            client_id=order.client_id,
            order_id=str(order.id),
            vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
            driver_id=str(order.driver_id) if order.driver_id else None,
            signal_type=LogisticsRiskSignalType.ETA_ANOMALY,
            severity=severity,
            ts=actual_end_at,
            explain={
                "signal_type": "ETA_ANOMALY",
                "route_id": None,
                "distance_to_nearest_stop_m": None,
                "time_delta_minutes": error_minutes,
                "constraints": {
                    "eta_error_high_minutes": ETA_ACCURACY_DEFAULTS.eta_error_high_minutes,
                    "eta_error_medium_minutes": ETA_ACCURACY_DEFAULTS.eta_error_medium_minutes,
                },
                "recommendation": "Review ETA accuracy for this order",
            },
        )
        db.add(signal)
        db.flush()
        signal_id = str(signal.id)
        db.commit()
        signal = repository.refresh_by_id(db, signal, LogisticsRiskSignal, signal_id)

        events.audit_event(
            db,
            event_type=events.LOGISTICS_RISK_SIGNAL_EMITTED,
            entity_type="logistics_risk_signal",
            entity_id=str(signal.id),
            payload={
                "order_id": str(order.id),
                "signal_type": signal.signal_type.value,
                "severity": signal.severity,
            },
            request_ctx=request_ctx,
        )
        events.register_risk_signal_node(
            db,
            tenant_id=order.tenant_id,
            order_id=str(order.id),
            signal_id=str(signal.id),
            request_ctx=request_ctx,
        )
        logistics_metrics.inc("logistics_eta_anomaly_total")
    return accuracy

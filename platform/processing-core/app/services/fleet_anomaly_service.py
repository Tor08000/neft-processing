from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import statistics
from typing import Any

from sqlalchemy.orm import Session

from app.models.cases import CaseEventType
from app.models.fuel import (
    FleetNotificationSeverity,
    FuelAnomaly,
    FuelAnomalyStatus,
    FuelAnomalyType,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelTransaction,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.decision_memory.records import record_decision_memory
from app.services.fleet_metrics import metrics as fleet_metrics

INJECTED_ANOMALY_MAP = {
    "VELOCITY_BURST": FuelAnomalyType.FREQUENCY_BURST,
    "GEO_JUMP": FuelAnomalyType.GEO_DISTANCE,
    "AMOUNT_SPIKE": FuelAnomalyType.SPIKE_AMOUNT,
    "LITERS_SPIKE": FuelAnomalyType.SPIKE_VOLUME,
    "OFF_HOURS": FuelAnomalyType.TIME_OF_DAY,
    "PRICE_MISMATCH": FuelAnomalyType.MERCHANT_OUTLIER,
    "STATION_SUSPECT": FuelAnomalyType.MERCHANT_OUTLIER,
}


@dataclass(frozen=True)
class BaselineSnapshot:
    amounts: list[Decimal]
    volumes: list[Decimal]
    merchants: set[str]
    hour_hist: dict[int, int]

    @property
    def count(self) -> int:
        return len(self.amounts)

    @property
    def avg_amount(self) -> Decimal | None:
        if not self.amounts:
            return None
        return sum(self.amounts) / Decimal(len(self.amounts))


def _percentile(values: list[Decimal], pct: float) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * pct / 100
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    fraction = Decimal(str(idx - lower))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _severity_from_ratio(ratio: Decimal) -> FleetNotificationSeverity:
    if ratio >= Decimal("3"):
        return FleetNotificationSeverity.CRITICAL
    if ratio >= Decimal("2"):
        return FleetNotificationSeverity.HIGH
    if ratio >= Decimal("1.5"):
        return FleetNotificationSeverity.MEDIUM
    return FleetNotificationSeverity.LOW


def _score_from_ratio(ratio: Decimal) -> Decimal:
    normalized = min(Decimal("1"), ratio / Decimal("3"))
    return normalized


def _baseline_for_card(db: Session, *, tx: FuelTransaction) -> BaselineSnapshot:
    window_start = tx.occurred_at - timedelta(days=30)
    rows = (
        db.query(FuelTransaction.amount, FuelTransaction.volume_liters, FuelTransaction.merchant_key, FuelTransaction.occurred_at)
        .filter(FuelTransaction.card_id == tx.card_id)
        .filter(FuelTransaction.occurred_at >= window_start)
        .filter(FuelTransaction.occurred_at < tx.occurred_at)
        .all()
    )
    amounts: list[Decimal] = []
    volumes: list[Decimal] = []
    merchants: set[str] = set()
    hour_hist: dict[int, int] = {}
    for amount, volume, merchant_key, occurred_at in rows:
        if amount is not None:
            amounts.append(Decimal(str(amount)))
        if volume is not None:
            volumes.append(Decimal(str(volume)))
        if merchant_key:
            merchants.add(str(merchant_key))
        if occurred_at:
            hour = occurred_at.astimezone(timezone.utc).hour
            hour_hist[hour] = hour_hist.get(hour, 0) + 1
    return BaselineSnapshot(amounts=amounts, volumes=volumes, merchants=merchants, hour_hist=hour_hist)


def _record_anomaly(
    db: Session,
    *,
    tx: FuelTransaction,
    anomaly_type: FuelAnomalyType,
    severity: FleetNotificationSeverity,
    score: Decimal,
    baseline: dict[str, Any],
    details: dict[str, Any],
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FuelAnomaly:
    event_id = fleet_service._emit_event(
        db,
        client_id=tx.client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.FUEL_ANOMALY_DETECTED,
        payload={
            "tx_id": str(tx.id),
            "anomaly_type": anomaly_type.value,
            "severity": severity.value,
            "score": str(score),
            "details": details,
        },
    )
    anomaly = FuelAnomaly(
        client_id=tx.client_id,
        card_id=tx.card_id,
        group_id=None,
        tx_id=tx.id,
        anomaly_type=anomaly_type,
        severity=severity,
        score=score,
        baseline=redact_deep(baseline, "", include_hash=True),
        details=redact_deep(details, "", include_hash=True),
        status=FuelAnomalyStatus.OPEN,
        occurred_at=tx.occurred_at,
        audit_event_id=event_id,
    )
    db.add(anomaly)
    db.flush()
    fleet_metrics.mark_anomaly(anomaly_type.value, severity.value)
    fleet_metrics.adjust_alerts_open(1)
    record_decision_memory(
        db,
        case_id=None,
        decision_type="anomaly",
        decision_ref_id=str(tx.id),
        decision_at=tx.occurred_at,
        decided_by_user_id=str(principal.user_id) if principal and principal.user_id else None,
        context_snapshot={"anomaly_type": anomaly_type.value, "details": details},
        rationale="anomaly_detected",
        score_snapshot={"score": float(score)},
        mastery_snapshot=None,
        audit_event_id=event_id,
    )
    return anomaly


def detect_anomalies_for_transaction(
    db: Session,
    *,
    transaction: FuelTransaction,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> list[FuelAnomaly]:
    baseline = _baseline_for_card(db, tx=transaction)
    anomalies: list[FuelAnomaly] = []

    if transaction.amount is not None and baseline.count >= 3:
        avg = baseline.avg_amount or Decimal("0")
        try:
            stddev = Decimal(str(statistics.pstdev([float(amount) for amount in baseline.amounts])))
        except statistics.StatisticsError:
            stddev = Decimal("0")
        p95 = _percentile(baseline.amounts, 95) or avg
        threshold = max(p95 * Decimal("1.3"), avg + (stddev * Decimal("3")))
        amount = Decimal(str(transaction.amount))
        if threshold > 0 and amount > threshold:
            ratio = amount / threshold
            severity = _severity_from_ratio(ratio)
            anomalies.append(
                _record_anomaly(
                    db,
                    tx=transaction,
                    anomaly_type=FuelAnomalyType.SPIKE_AMOUNT,
                    severity=severity,
                    score=_score_from_ratio(ratio),
                    baseline={"avg": str(avg), "p95": str(p95), "stddev": str(stddev)},
                    details={"reason": "amount_spike", "threshold": str(threshold), "amount": str(amount)},
                    principal=principal,
                    request_id=request_id,
                    trace_id=trace_id,
                )
            )

    if transaction.volume_liters is not None and baseline.count >= 3 and baseline.volumes:
        avg = sum(baseline.volumes) / Decimal(len(baseline.volumes))
        try:
            stddev = Decimal(str(statistics.pstdev([float(volume) for volume in baseline.volumes])))
        except statistics.StatisticsError:
            stddev = Decimal("0")
        p95 = _percentile(baseline.volumes, 95) or avg
        threshold = max(p95 * Decimal("1.3"), avg + (stddev * Decimal("3")))
        volume = Decimal(str(transaction.volume_liters))
        if threshold > 0 and volume > threshold:
            ratio = volume / threshold
            severity = _severity_from_ratio(ratio)
            anomalies.append(
                _record_anomaly(
                    db,
                    tx=transaction,
                    anomaly_type=FuelAnomalyType.SPIKE_VOLUME,
                    severity=severity,
                    score=_score_from_ratio(ratio),
                    baseline={"avg": str(avg), "p95": str(p95), "stddev": str(stddev)},
                    details={"reason": "volume_spike", "threshold": str(threshold), "volume": str(volume)},
                    principal=principal,
                    request_id=request_id,
                    trace_id=trace_id,
                )
            )

    if transaction.merchant_key and baseline.merchants and transaction.merchant_key not in baseline.merchants:
        anomalies.append(
            _record_anomaly(
                db,
                tx=transaction,
                anomaly_type=FuelAnomalyType.NEW_MERCHANT,
                severity=FleetNotificationSeverity.MEDIUM,
                score=Decimal("0.4"),
                baseline={"merchant_count": len(baseline.merchants)},
                details={"reason": "merchant_not_seen", "merchant_key": transaction.merchant_key},
                principal=principal,
                request_id=request_id,
                trace_id=trace_id,
            )
        )

    window_start = transaction.occurred_at - timedelta(minutes=10)
    recent_count = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.card_id == transaction.card_id)
        .filter(FuelTransaction.occurred_at >= window_start)
        .filter(FuelTransaction.occurred_at <= transaction.occurred_at)
        .count()
    )
    if recent_count >= 3:
        anomalies.append(
            _record_anomaly(
                db,
                tx=transaction,
                anomaly_type=FuelAnomalyType.FREQUENCY_BURST,
                severity=FleetNotificationSeverity.HIGH,
                score=Decimal("0.7"),
                baseline={"window_minutes": 10, "recent_count": recent_count},
                details={"reason": "frequency_burst", "count": recent_count},
                principal=principal,
                request_id=request_id,
                trace_id=trace_id,
            )
        )

    total_hours = sum(baseline.hour_hist.values())
    if total_hours >= 10:
        tx_hour = transaction.occurred_at.astimezone(timezone.utc).hour
        hour_count = baseline.hour_hist.get(tx_hour, 0)
        share = hour_count / total_hours if total_hours else 0
        if tx_hour <= 5 and share < 0.1:
            severity = FleetNotificationSeverity.HIGH if share < 0.05 else FleetNotificationSeverity.MEDIUM
            anomalies.append(
                _record_anomaly(
                    db,
                    tx=transaction,
                    anomaly_type=FuelAnomalyType.TIME_OF_DAY,
                    severity=severity,
                    score=Decimal("0.6"),
                    baseline={"hour_share": share, "hour": tx_hour},
                    details={"reason": "rare_time_window", "hour": tx_hour},
                    principal=principal,
                    request_id=request_id,
                    trace_id=trace_id,
                )
            )

    return anomalies


def detect_injected_anomalies(
    db: Session,
    *,
    transaction: FuelTransaction,
    raw_payload: dict[str, Any] | None,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> list[FuelAnomaly]:
    if not raw_payload:
        return []
    injected = raw_payload.get("virtual_anomalies") or raw_payload.get("anomalies") or []
    anomalies: list[FuelAnomaly] = []
    for entry in injected:
        if not entry:
            continue
        if isinstance(entry, dict):
            name = str(entry.get("type") or entry.get("name") or "").upper()
            severity = entry.get("severity")
        else:
            name = str(entry).upper()
            severity = None
        anomaly_type = INJECTED_ANOMALY_MAP.get(name)
        if not anomaly_type:
            try:
                anomaly_type = FuelAnomalyType(name)
            except ValueError:
                continue
        severity_value = FleetNotificationSeverity(severity) if severity else FleetNotificationSeverity.MEDIUM
        anomalies.append(
            _record_synthetic_anomaly(
                db,
                client_id=transaction.client_id,
                card_id=str(transaction.card_id),
                group_id=None,
                anomaly_type=anomaly_type,
                severity=severity_value,
                score=Decimal("0.7"),
                occurred_at=transaction.occurred_at,
                details={"source": "virtual_network", "injected_type": name},
                principal=principal,
                request_id=request_id,
                trace_id=trace_id,
            )
        )
    return anomalies


def _record_synthetic_anomaly(
    db: Session,
    *,
    client_id: str,
    card_id: str | None,
    group_id: str | None,
    anomaly_type: FuelAnomalyType,
    severity: FleetNotificationSeverity,
    score: Decimal,
    occurred_at: datetime,
    details: dict[str, Any],
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FuelAnomaly:
    event_id = fleet_service._emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.FUEL_ANOMALY_DETECTED,
        payload={
            "anomaly_type": anomaly_type.value,
            "severity": severity.value,
            "score": str(score),
            "details": details,
        },
    )
    anomaly = FuelAnomaly(
        client_id=client_id,
        card_id=card_id,
        group_id=group_id,
        tx_id=None,
        anomaly_type=anomaly_type,
        severity=severity,
        score=score,
        baseline=None,
        details=redact_deep(details, "", include_hash=True),
        status=FuelAnomalyStatus.OPEN,
        occurred_at=occurred_at,
        audit_event_id=event_id,
    )
    db.add(anomaly)
    db.flush()
    fleet_metrics.mark_anomaly(anomaly_type.value, severity.value)
    fleet_metrics.adjust_alerts_open(1)
    record_decision_memory(
        db,
        case_id=None,
        decision_type="anomaly",
        decision_ref_id=str(anomaly.id),
        decision_at=occurred_at,
        decided_by_user_id=str(principal.user_id) if principal and principal.user_id else None,
        context_snapshot={"anomaly_type": anomaly_type.value, "details": details},
        rationale="synthetic_anomaly_detected",
        score_snapshot={"score": float(score)},
        mastery_snapshot=None,
        audit_event_id=event_id,
    )
    return anomaly


def detect_repeated_breach_anomaly(
    db: Session,
    *,
    breach: FuelLimitBreach,
    card_id: str | None,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
    window_minutes: int = 60,
    threshold: int = 3,
) -> FuelAnomaly | None:
    if not card_id:
        return None
    window_start = breach.occurred_at - timedelta(minutes=window_minutes)
    existing = (
        db.query(FuelAnomaly)
        .filter(FuelAnomaly.card_id == card_id)
        .filter(FuelAnomaly.anomaly_type == FuelAnomalyType.REPEATED_BREACH)
        .filter(FuelAnomaly.occurred_at >= window_start)
        .one_or_none()
    )
    if existing:
        return None
    breach_count = (
        db.query(FuelLimitBreach)
        .filter(FuelLimitBreach.client_id == breach.client_id)
        .filter(FuelLimitBreach.scope_type == FuelLimitBreachScopeType.CARD)
        .filter(FuelLimitBreach.scope_id == card_id)
        .filter(FuelLimitBreach.occurred_at >= window_start)
        .filter(FuelLimitBreach.occurred_at <= breach.occurred_at)
        .count()
    )
    if breach_count < threshold:
        return None
    return _record_synthetic_anomaly(
        db,
        client_id=breach.client_id,
        card_id=card_id,
        group_id=None,
        anomaly_type=FuelAnomalyType.REPEATED_BREACH,
        severity=FleetNotificationSeverity.HIGH,
        score=Decimal("0.7"),
        occurred_at=breach.occurred_at,
        details={
            "reason": "repeated_breach",
            "breach_id": str(breach.id),
            "count": breach_count,
            "window_minutes": window_minutes,
        },
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


__all__ = ["detect_anomalies_for_transaction", "detect_injected_anomalies", "detect_repeated_breach_anomaly"]

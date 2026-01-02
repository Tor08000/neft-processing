from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cases import CaseEventType
from app.models.fleet import FuelCardGroupMember
from app.models.fuel import (
    FuelLimit,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachStatus,
    FuelLimitBreachType,
    FuelLimitCheckStatus,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelTransaction,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.decision_memory.records import record_decision_memory
from app.services.fleet_metrics import metrics as fleet_metrics


@dataclass(frozen=True)
class PeriodWindow:
    start: datetime
    end: datetime


def _period_window(occurred_at: datetime, period: FuelLimitPeriod) -> PeriodWindow:
    ts = occurred_at.astimezone(timezone.utc)
    if period == FuelLimitPeriod.DAILY:
        start = datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
    elif period == FuelLimitPeriod.WEEKLY:
        weekday = ts.weekday()
        start = datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc) - timedelta(days=weekday)
        end = start + timedelta(days=7)
    else:
        start = datetime(ts.year, ts.month, 1, tzinfo=timezone.utc)
        if ts.month == 12:
            end = datetime(ts.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(ts.year, ts.month + 1, 1, tzinfo=timezone.utc)
    return PeriodWindow(start=start, end=end)


def _sum_scope_spend(
    db: Session,
    *,
    card_ids: list[str],
    window: PeriodWindow,
) -> tuple[Decimal, Decimal]:
    if not card_ids:
        return Decimal("0"), Decimal("0")
    amount, volume = (
        db.query(
            func.coalesce(func.sum(FuelTransaction.amount), 0),
            func.coalesce(func.sum(FuelTransaction.volume_liters), 0),
        )
        .filter(FuelTransaction.card_id.in_(card_ids))
        .filter(FuelTransaction.occurred_at >= window.start)
        .filter(FuelTransaction.occurred_at < window.end)
        .one()
    )
    return Decimal(str(amount)), Decimal(str(volume))


def _limit_categories(limit: FuelLimit) -> tuple[list[str], list[str]]:
    categories = limit.categories or {}
    allowlist = categories.get("allowlist") or categories.get("allowed") or []
    denylist = categories.get("denylist") or categories.get("blocked") or []
    return [str(item).upper() for item in allowlist], [str(item).upper() for item in denylist]


def _stations_allowlist(limit: FuelLimit) -> list[str]:
    stations = limit.stations_allowlist or {}
    allowlist = stations.get("allowlist") or stations.get("stations") or []
    return [str(item) for item in allowlist]


def apply_limit_checks(
    db: Session,
    *,
    transaction: FuelTransaction,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> list[FuelLimitBreach]:
    limits = (
        db.query(FuelLimit)
        .filter(FuelLimit.client_id == transaction.client_id)
        .filter(FuelLimit.active.is_(True))
        .filter(FuelLimit.scope_type.in_([FuelLimitScopeType.CARD, FuelLimitScopeType.CARD_GROUP]))
        .all()
    )
    if not limits:
        transaction.limit_check_status = FuelLimitCheckStatus.OK
        return []

    card_limits = [limit for limit in limits if limit.scope_type == FuelLimitScopeType.CARD]
    group_limits = [limit for limit in limits if limit.scope_type == FuelLimitScopeType.CARD_GROUP]

    breaches: list[FuelLimitBreach] = []
    check_status = FuelLimitCheckStatus.OK
    details: list[dict[str, Any]] = []

    def _apply_limit(limit: FuelLimit, scope_type: FuelLimitBreachScopeType, scope_id: str, card_ids: list[str]) -> None:
        nonlocal check_status
        window = _period_window(transaction.occurred_at, limit.period)
        amount, volume = _sum_scope_spend(db, card_ids=card_ids, window=window)
        category = (transaction.category or "").upper()
        allowlist, denylist = _limit_categories(limit)
        stations_allowlist = _stations_allowlist(limit)

        if limit.amount_limit is not None and amount > Decimal(str(limit.amount_limit)):
            breach = _record_breach(
                limit,
                scope_type=scope_type,
                scope_id=scope_id,
                breach_type=FuelLimitBreachType.AMOUNT,
                threshold=Decimal(str(limit.amount_limit)),
                observed=amount,
                tx_id=str(transaction.id),
            )
            breaches.append(breach)
            check_status = FuelLimitCheckStatus.HARD_BREACH
        if limit.volume_limit_liters is not None and volume > Decimal(str(limit.volume_limit_liters)):
            breach = _record_breach(
                limit,
                scope_type=scope_type,
                scope_id=scope_id,
                breach_type=FuelLimitBreachType.VOLUME,
                threshold=Decimal(str(limit.volume_limit_liters)),
                observed=volume,
                tx_id=str(transaction.id),
            )
            breaches.append(breach)
            check_status = FuelLimitCheckStatus.HARD_BREACH
        if category and denylist and category in denylist:
            breach = _record_breach(
                limit,
                scope_type=scope_type,
                scope_id=scope_id,
                breach_type=FuelLimitBreachType.CATEGORY,
                threshold=Decimal("0"),
                observed=Decimal("1"),
                tx_id=str(transaction.id),
            )
            breaches.append(breach)
            check_status = FuelLimitCheckStatus.HARD_BREACH
        if category and allowlist and category not in allowlist:
            breach = _record_breach(
                limit,
                scope_type=scope_type,
                scope_id=scope_id,
                breach_type=FuelLimitBreachType.CATEGORY,
                threshold=Decimal("1"),
                observed=Decimal("0"),
                tx_id=str(transaction.id),
            )
            breaches.append(breach)
            if check_status != FuelLimitCheckStatus.HARD_BREACH:
                check_status = FuelLimitCheckStatus.SOFT_BREACH
        if stations_allowlist and transaction.station_external_id not in stations_allowlist:
            breach = _record_breach(
                limit,
                scope_type=scope_type,
                scope_id=scope_id,
                breach_type=FuelLimitBreachType.STATION,
                threshold=Decimal("1"),
                observed=Decimal("0"),
                tx_id=str(transaction.id),
            )
            breaches.append(breach)
            check_status = FuelLimitCheckStatus.HARD_BREACH
        if breaches:
            details.append(
                {
                    "limit_id": str(limit.id),
                    "scope_type": scope_type.value,
                    "scope_id": scope_id,
                    "period": limit.period.value,
                    "amount": str(amount),
                    "volume_liters": str(volume),
                }
            )
    def _record_breach(
        limit: FuelLimit,
        *,
        scope_type: FuelLimitBreachScopeType,
        scope_id: str,
        breach_type: FuelLimitBreachType,
        threshold: Decimal,
        observed: Decimal,
        tx_id: str | None,
    ) -> FuelLimitBreach:
        delta = observed - threshold
        event_id = fleet_service._emit_event(
            db,
            client_id=transaction.client_id,
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
            event_type=CaseEventType.FUEL_LIMIT_BREACH_DETECTED,
            payload={
                "limit_id": str(limit.id),
                "scope_type": scope_type.value,
                "scope_id": scope_id,
                "breach_type": breach_type.value,
                "threshold": str(threshold),
                "observed": str(observed),
                "delta": str(delta),
                "tx_id": tx_id,
            },
        )
        record_decision_memory(
            db,
            case_id=None,
            decision_type="limit_breach",
            decision_ref_id=str(limit.id),
            decision_at=transaction.occurred_at,
            decided_by_user_id=str(principal.user_id) if principal and principal.user_id else None,
            context_snapshot=redact_deep(
                {
                    "limit_id": str(limit.id),
                    "scope_type": scope_type.value,
                    "scope_id": scope_id,
                    "breach_type": breach_type.value,
                    "threshold": str(threshold),
                    "observed": str(observed),
                    "delta": str(delta),
                    "tx_id": tx_id,
                },
                "",
                include_hash=True,
            ),
            rationale="limit_breach_detected",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=event_id,
        )
        fleet_metrics.mark_limit_breach(breach_type.value, scope_type.value)
        breach = FuelLimitBreach(
            client_id=transaction.client_id,
            scope_type=scope_type,
            scope_id=scope_id,
            period=limit.period,
            limit_id=limit.id,
            breach_type=breach_type,
            threshold=threshold,
            observed=observed,
            delta=delta,
            occurred_at=transaction.occurred_at,
            tx_id=tx_id,
            status=FuelLimitBreachStatus.OPEN,
            audit_event_id=event_id,
        )
        db.add(breach)
        return breach

    if card_limits:
        for limit in card_limits:
            if str(limit.scope_id) != str(transaction.card_id):
                continue
            _apply_limit(limit, FuelLimitBreachScopeType.CARD, str(transaction.card_id), [str(transaction.card_id)])
    if group_limits:
        group_ids = (
            db.query(FuelCardGroupMember.group_id)
            .filter(FuelCardGroupMember.card_id == transaction.card_id)
            .filter(FuelCardGroupMember.removed_at.is_(None))
            .all()
        )
        for group_id in [row[0] for row in group_ids]:
            card_ids = (
                db.query(FuelCardGroupMember.card_id)
                .filter(FuelCardGroupMember.group_id == group_id)
                .filter(FuelCardGroupMember.removed_at.is_(None))
                .all()
            )
            for limit in group_limits:
                if str(limit.scope_id) != str(group_id):
                    continue
                _apply_limit(
                    limit=limit,
                    scope_type=FuelLimitBreachScopeType.GROUP,
                    scope_id=str(group_id),
                    card_ids=[str(row[0]) for row in card_ids],
                )
    transaction.limit_check_status = check_status
    transaction.limit_check_details = redact_deep(
        {"status": check_status.value, "breaches": details}, "", include_hash=True
    )
    return breaches


__all__ = ["apply_limit_checks"]

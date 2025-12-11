from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.models.contract_limits import LimitConfig, LimitScope, LimitType, LimitWindow
from app.models.operation import Operation, OperationStatus

logger = get_logger(__name__)

SUCCESS_STATUSES = {
    OperationStatus.APPROVED,
    OperationStatus.AUTHORIZED,
    OperationStatus.HELD,
    OperationStatus.POSTED,
    OperationStatus.COMPLETED,
}


@dataclass
class Consumption:
    used: float
    projected: float
    limit: LimitConfig
    window_start: datetime

    @property
    def remaining(self) -> float:
        return max(0.0, float(self.limit.value) - float(self.projected))


@dataclass
class LimitEvaluation:
    approved: bool
    violations: List[Consumption]


def _window_start(config: LimitConfig, *, now: datetime) -> datetime:
    if config.window == LimitWindow.MONTH or config.limit_type == LimitType.MONTHLY_AMOUNT:
        return datetime(now.year, now.month, 1, tzinfo=now.tzinfo or timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=now.tzinfo or timezone.utc)


def _base_query(db: Session, config: LimitConfig, *, start: datetime):
    query = db.query(Operation).filter(Operation.created_at >= start)
    query = query.filter(Operation.status.in_(SUCCESS_STATUSES))
    if config.scope == LimitScope.CLIENT:
        query = query.filter(Operation.client_id == config.subject_ref)
    elif config.scope == LimitScope.CARD:
        query = query.filter(Operation.card_id == config.subject_ref)
    elif config.scope == LimitScope.TARIFF:
        query = query.filter(Operation.tariff_id == config.subject_ref)
    return query


def _usage_value(query, config: LimitConfig) -> float:
    if config.limit_type == LimitType.DAILY_VOLUME:
        return float(query.count())
    # amount-based
    total = query.with_entities(func.coalesce(func.sum(Operation.amount), 0)).scalar()
    return float(total or 0)


def calculate_consumption(
    db: Session,
    config: LimitConfig,
    *,
    amount: float,
    volume: float,
    now: Optional[datetime] = None,
) -> Consumption:
    now = now or datetime.now(timezone.utc)
    start = _window_start(config, now=now)
    query = _base_query(db, config, start=start)
    used = _usage_value(query, config)
    increment = volume if config.limit_type == LimitType.DAILY_VOLUME else amount
    projected = used + increment
    return Consumption(used=used, projected=projected, limit=config, window_start=start)


def _matching_configs(
    db: Session, *, client_id: str, card_id: str, tariff_id: str | None = None
) -> Iterable[LimitConfig]:
    clauses = [
        (LimitConfig.scope == LimitScope.CLIENT, LimitConfig.subject_ref == client_id),
        (LimitConfig.scope == LimitScope.CARD, LimitConfig.subject_ref == card_id),
    ]
    if tariff_id:
        clauses.append((LimitConfig.scope == LimitScope.TARIFF, LimitConfig.subject_ref == tariff_id))

    query = db.query(LimitConfig).filter(LimitConfig.enabled.is_(True))
    scope_filters = []
    for scope_expr, subject_expr in clauses:
        scope_filters.append(scope_expr & subject_expr)
    if scope_filters:
        query = query.filter(or_(*scope_filters))
    return query.all()


def check_contractual_limits(
    db: Session,
    *,
    client_id: str,
    card_id: str,
    amount: float,
    quantity: float | None = None,
    tariff_id: str | None = None,
    now: Optional[datetime] = None,
) -> LimitEvaluation:
    """
    Evaluate contractual limits for the given operation context.

    Returns LimitEvaluation with violations populated when projected usage exceeds limit value.
    """

    quantity_value = quantity if quantity is not None else 1.0
    configs = _matching_configs(db, client_id=client_id, card_id=card_id, tariff_id=tariff_id)
    violations: List[Consumption] = []
    for cfg in configs:
        consumption = calculate_consumption(
            db,
            cfg,
            amount=float(amount),
            volume=float(quantity_value),
            now=now,
        )
        if consumption.projected > float(cfg.value):
            violations.append(consumption)

    return LimitEvaluation(approved=not violations, violations=violations)

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from neft_shared.logging_setup import get_logger
from sqlalchemy.orm import Session

from app.models.operation import Operation

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from app.services.risk_adapter import OperationContext, RiskResult

logger = get_logger(__name__)

DEFAULT_AMOUNT_THRESHOLD = int(os.getenv("RISK_AMOUNT_THRESHOLD", "100000"))
DEFAULT_GRAYLIST_TERMINALS = set(
    filter(None, os.getenv("RISK_GRAYLIST_TERMINALS", "").split(","))
)
DEFAULT_GRAYLIST_MERCHANTS = set(
    filter(None, os.getenv("RISK_GRAYLIST_MERCHANTS", "").split(","))
)
DEFAULT_NIGHT_START = int(os.getenv("RISK_NIGHT_START", "0"))
DEFAULT_NIGHT_END = int(os.getenv("RISK_NIGHT_END", "5"))
DEFAULT_HIGH_FREQUENCY_THRESHOLD = int(
    os.getenv("RISK_HIGH_FREQUENCY_THRESHOLD", "5")
)

# Mutable aliases used by tests and admin tooling
GRAYLIST_TERMINALS = set(DEFAULT_GRAYLIST_TERMINALS)
GRAYLIST_MERCHANTS = set(DEFAULT_GRAYLIST_MERCHANTS)

LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "MANUAL_REVIEW", "BLOCK"]
SCORE_MAP: dict[str, float] = {
    "LOW": 0.2,
    "MEDIUM": 0.5,
    "HIGH": 0.8,
    "BLOCK": 1.0,
    "MANUAL_REVIEW": 0.6,
}


class RuleScope(str, Enum):
    """Scope of a rule target.

    Attributes mirror UPAS DSL field ``scope`` and describe where the rule
    should be applied:

    * ``GLOBAL`` – applies to any operation.
    * ``CLIENT`` – limited to a specific client id.
    * ``CARD`` – limited to a specific card id.
    * ``TARIFF`` – limited to a specific tariff id.
    """

    GLOBAL = "GLOBAL"
    CLIENT = "CLIENT"
    CARD = "CARD"
    TARIFF = "TARIFF"


class MetricType(str, Enum):
    """Supported metrics in the UPAS risk DSL.

    They map to the ``metric`` field in the specification:

    * ``ALWAYS`` – unconditional rule trigger.
    * ``AMOUNT`` – compare single operation amount against ``value``.
    * ``QUANTITY`` – compare fuel quantity against ``value``.
    * ``COUNT`` – number of operations in a ``window``.
    * ``TOTAL_AMOUNT`` – cumulative amount in a ``window``.
    * ``AMOUNT_SPIKE`` – current amount above historical maximum multiplied
      by ``value``.
    * ``UNUSUAL_PRODUCT`` – product type not present in historical profile.
    """

    ALWAYS = "always"
    AMOUNT = "amount"
    QUANTITY = "quantity"
    COUNT = "count"
    TOTAL_AMOUNT = "total_amount"
    AMOUNT_SPIKE = "amount_spike"
    UNUSUAL_PRODUCT = "unusual_product"


class RuleAction(str, Enum):
    """Resulting action when a rule is triggered.

    Maps to the ``action`` field in DSL and is later translated to the
    unified risk levels.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass
class RuleSelector:
    """Attribute based selector to narrow rule applicability (``selector`` field).

    All attributes are optional. If provided, they restrict rule evaluation to
    matching values in :class:`~app.services.risk_adapter.OperationContext`.
    """

    product_types: set[str] | None = None
    merchant_ids: set[str] | None = None
    terminal_ids: set[str] | None = None
    geo: set[str] | None = None
    hours: Union[range, set[int], None] = None

    def matches(self, context: "OperationContext") -> bool:
        if self.product_types and (context.product_type not in self.product_types):
            return False
        if self.merchant_ids and (str(context.merchant_id) not in self.merchant_ids):
            return False
        if self.terminal_ids and (str(context.terminal_id) not in self.terminal_ids):
            return False
        if self.geo and (context.geo not in self.geo):
            return False
        if self.hours is not None and context.created_at.hour not in self.hours:
            return False
        return True


@dataclass
class RuleWindow:
    """Sliding window for aggregated metrics."""

    duration: timedelta

    @classmethod
    def hours(cls, value: int) -> "RuleWindow":
        return cls(duration=timedelta(hours=value))


@dataclass
class RuleDefinition:
    """Unified DSL rule definition (runtime representation).

    Mirrors UPAS fields:

    * ``name`` – identifier of the rule for audit/debugging.
    * ``scope`` / ``subject_id`` – define to which entity the rule is bound.
    * ``selector`` – attribute-based filter for geo/time/product, etc.
    * ``window`` – optional aggregation window for metrics like ``COUNT``.
    * ``metric`` / ``value`` – how to compute the check and threshold.
    * ``action`` – resulting decision level when triggered.
    * ``priority`` – lower number means earlier evaluation.
    * ``enabled`` – toggle rule execution.
    * ``reason`` – human readable reason to surface in risk payload.
    """

    name: str
    scope: RuleScope
    subject_id: str | None
    selector: RuleSelector
    metric: MetricType
    value: float
    action: RuleAction
    priority: int = 100
    enabled: bool = True
    window: RuleWindow | None = None
    reason: str | None = None

    def applies_to(self, context: "OperationContext") -> bool:
        if not self.enabled:
            return False
        if self.scope == RuleScope.GLOBAL:
            return True
        if self.scope == RuleScope.CLIENT:
            return self.subject_id == str(context.client_id)
        if self.scope == RuleScope.CARD:
            return self.subject_id == str(context.card_id)
        if self.scope == RuleScope.TARIFF:
            return self.subject_id == (context.tariff_id if context.tariff_id else None)
        return False

    def evaluate(
        self,
        context: "OperationContext",
        stats: "RecentStats",
        window_operations: Sequence[Operation],
    ) -> tuple[bool, dict[str, Any]]:
        if not self.applies_to(context):
            return False, {}
        if not self.selector.matches(context):
            return False, {}

        measured: float | None = None
        if self.metric == MetricType.ALWAYS:
            measured = 1.0
            triggered = True
        elif self.metric == MetricType.AMOUNT:
            measured = float(context.amount)
            triggered = measured >= self.value
        elif self.metric == MetricType.QUANTITY:
            measured = float(context.quantity or 0)
            triggered = measured >= self.value
        elif self.metric == MetricType.COUNT:
            measured = len(window_operations)
            triggered = measured > self.value
        elif self.metric == MetricType.TOTAL_AMOUNT:
            measured = sum(op.amount for op in window_operations) + float(context.amount)
            triggered = measured >= self.value
        elif self.metric == MetricType.AMOUNT_SPIKE:
            measured = float(context.amount)
            triggered = bool(stats.max_amount and measured > stats.max_amount * self.value)
        elif self.metric == MetricType.UNUSUAL_PRODUCT:
            measured = 1.0 if context.product_type else 0.0
            triggered = bool(
                context.product_type
                and stats.usual_product_types is not None
                and context.product_type not in stats.usual_product_types
            )
        else:
            triggered = False

        if not triggered:
            return False, {}

        flags = {"metric": self.metric.value, "measured": measured, "threshold": self.value}
        if self.reason:
            flags["reason"] = self.reason
        return True, flags


class WindowConfig(BaseModel):
    """DSL wrapper for ``window``.

    Supports explicit duration in seconds or helper ``hours`` shortcut.
    Exactly one of the fields must be provided.
    """

    duration_seconds: Optional[int] = Field(
        None, description="Explicit window duration in seconds (positive)."
    )
    hours: Optional[int] = Field(None, description="Shortcut to set window by hours.")

    @model_validator(mode="after")
    def _only_one(self) -> "WindowConfig":
        provided = [
            name
            for name, value in {
                "duration_seconds": self.duration_seconds,
                "hours": self.hours,
            }.items()
            if value is not None
        ]
        if len(provided) != 1:
            raise ValueError("Provide exactly one of duration_seconds or hours")
        return self

    @field_validator("duration_seconds", "hours")
    def _positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("Window duration must be positive")
        return value

    def to_window(self) -> RuleWindow:
        if self.hours is not None:
            return RuleWindow.hours(self.hours)
        assert self.duration_seconds is not None  # validated above
        return RuleWindow(duration=timedelta(seconds=self.duration_seconds))


class SelectorConfig(BaseModel):
    """DSL wrapper for ``selector`` field."""

    product_types: Optional[set[str]] = Field(None, description="Allowed product types")
    merchant_ids: Optional[set[str]] = Field(None, description="Allowed merchant ids")
    terminal_ids: Optional[set[str]] = Field(None, description="Allowed terminal ids")
    geo: Optional[set[str]] = Field(None, description="Allowed geo codes")
    hours: Optional[list[int]] = Field(
        None, description="Hours of day (0-23) when the rule should be applied"
    )

    @field_validator("hours")
    def _validate_hours(cls, value: Optional[list[int]]) -> Optional[list[int]]:
        if value is None:
            return None
        invalid = [hour for hour in value if hour < 0 or hour > 23]
        if invalid:
            raise ValueError(f"Hours must be between 0 and 23. Got {invalid}")
        return value

    def to_selector(self) -> RuleSelector:
        hours_range: Union[set[int], range, None]
        hours_range = set(self.hours) if self.hours is not None else None
        return RuleSelector(
            product_types=self.product_types,
            merchant_ids=self.merchant_ids,
            terminal_ids=self.terminal_ids,
            geo=self.geo,
            hours=hours_range,
        )


class RuleConfig(BaseModel):
    """Full DSL rule specification.

    This model is aligned with UPAS Part V fields and can be stored/transported
    as JSON. Conversion to :class:`RuleDefinition` is available via
    :meth:`to_definition`.
    """

    name: str = Field(..., description="Unique rule name")
    scope: RuleScope = Field(..., description="Scope of the rule application")
    subject_id: Optional[str] = Field(
        None, description="Identifier within the chosen scope (e.g. client id)"
    )
    selector: SelectorConfig = Field(
        default_factory=SelectorConfig,
        description="Attribute-based filter to narrow applicability",
    )
    window: Optional[WindowConfig] = Field(
        None, description="Optional sliding window for aggregated metrics"
    )
    metric: MetricType = Field(..., description="Metric to evaluate")
    value: float = Field(..., description="Threshold or expected value")
    action: RuleAction = Field(..., description="Action to take when triggered")
    priority: int = Field(100, description="Evaluation order: lower first")
    enabled: bool = Field(True, description="Whether rule is active")
    reason: Optional[str] = Field(None, description="Human readable reason")

    def to_definition(self) -> RuleDefinition:
        return RuleDefinition(
            name=self.name,
            scope=self.scope,
            subject_id=self.subject_id,
            selector=self.selector.to_selector(),
            metric=self.metric,
            value=self.value,
            action=self.action,
            priority=self.priority,
            enabled=self.enabled,
            window=self.window.to_window() if self.window else None,
            reason=self.reason,
        )


@dataclass
class RecentStats:
    avg_amount: float = 0.0
    max_amount: int = 0
    operations_count_last_24h: int = 0
    operations_count_last_hour: int = 0
    usual_product_types: set[str] | None = None


def _severity(value: str) -> int:
    try:
        return LEVEL_ORDER.index(value.upper())
    except ValueError:
        return LEVEL_ORDER.index("MEDIUM")


def _raise_level(current: str, desired: str) -> str:
    return desired if _severity(desired) > _severity(current) else current


def _compute_score(level: str, reasons: Iterable[str]) -> float:
    base = SCORE_MAP.get(level.upper(), SCORE_MAP["MEDIUM"])
    bump = min(0.2, 0.05 * len(list(reasons)))
    return min(1.0, base + bump)


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _load_operations(
    db: Optional[Session],
    context: "OperationContext",
    window: RuleWindow,
    now: datetime,
) -> list[Operation]:
    if db is None:
        return []

    from_ts = now - window.duration
    return (
        db.query(Operation)
        .filter(
            Operation.card_id == str(context.card_id),
            Operation.client_id == str(context.client_id),
            Operation.created_at >= from_ts,
        )
        .all()
    )


def _default_rules() -> list[RuleDefinition]:
    amount_threshold = int(
        os.getenv("RISK_AMOUNT_THRESHOLD", os.getenv("RISK_HIGH_THRESHOLD", str(DEFAULT_AMOUNT_THRESHOLD)))
    )
    graylist_terminals = GRAYLIST_TERMINALS or set(
        filter(None, os.getenv("RISK_GRAYLIST_TERMINALS", "").split(","))
    )
    graylist_merchants = GRAYLIST_MERCHANTS or set(
        filter(None, os.getenv("RISK_GRAYLIST_MERCHANTS", "").split(","))
    )
    night_start = int(os.getenv("RISK_NIGHT_START", str(DEFAULT_NIGHT_START)))
    night_end = int(os.getenv("RISK_NIGHT_END", str(DEFAULT_NIGHT_END)))
    frequency_threshold = int(
        os.getenv("RISK_HIGH_FREQUENCY_THRESHOLD", str(DEFAULT_HIGH_FREQUENCY_THRESHOLD))
    )

    night_hours = range(night_start, night_end)
    selector_night = RuleSelector(hours=night_hours)

    return [
        RuleDefinition(
            name="amount_above_threshold",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.AMOUNT,
            value=amount_threshold,
            action=RuleAction.MEDIUM,
            priority=50,
            reason="amount_above_threshold",
        ),
        RuleDefinition(
            name="night_operation",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=selector_night,
            metric=MetricType.ALWAYS,
            value=1,
            action=RuleAction.LOW,
            priority=60,
            reason="night_operation",
        ),
        RuleDefinition(
            name="night_high_amount",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=selector_night,
            metric=MetricType.AMOUNT,
            value=amount_threshold / 2,
            action=RuleAction.MEDIUM,
            priority=55,
            reason="night_high_amount",
        ),
        RuleDefinition(
            name="graylisted_terminal",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(terminal_ids=graylist_terminals),
            metric=MetricType.ALWAYS,
            value=1,
            action=RuleAction.HIGH,
            priority=10,
            reason="graylisted_terminal",
            enabled=bool(graylist_terminals),
        ),
        RuleDefinition(
            name="graylisted_merchant",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(merchant_ids=graylist_merchants),
            metric=MetricType.ALWAYS,
            value=1,
            action=RuleAction.HIGH,
            priority=10,
            reason="graylisted_merchant",
            enabled=bool(graylist_merchants),
        ),
        RuleDefinition(
            name="amount_spike",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.AMOUNT_SPIKE,
            value=2.0,
            action=RuleAction.HIGH,
            priority=40,
            reason="amount_spike",
        ),
        RuleDefinition(
            name="high_frequency",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.COUNT,
            value=frequency_threshold,
            action=RuleAction.HIGH,
            priority=45,
            window=RuleWindow.hours(1),
            reason="high_frequency",
        ),
        RuleDefinition(
            name="unusual_fuel_type",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=RuleSelector(),
            metric=MetricType.UNUSUAL_PRODUCT,
            value=1,
            action=RuleAction.MEDIUM,
            priority=70,
            reason="unusual_fuel_type",
        ),
    ]


RuleLike = Union[RuleDefinition, RuleConfig]


def _normalize_rules(rules: Iterable[RuleLike] | None) -> list[RuleDefinition]:
    """Ensure incoming rules (DSL configs or runtime definitions) are unified."""

    source = list(rules or _default_rules())
    definitions: list[RuleDefinition] = []
    for rule in source:
        if isinstance(rule, RuleDefinition):
            definitions.append(rule)
        else:
            definitions.append(rule.to_definition())
    return sorted(definitions, key=lambda rule: rule.priority)


async def load_recent_operations_stats(
    db: Optional[Session], card_id: Any, client_id: Any, now: Optional[datetime] = None
) -> RecentStats:
    if db is None:
        return RecentStats()

    now = _normalize_dt(now) or datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    last_day = now - timedelta(days=1)
    last_hour = now - timedelta(hours=1)

    base_query = db.query(Operation).filter(
        Operation.card_id == str(card_id),
        Operation.client_id == str(client_id),
        Operation.created_at >= month_ago,
    )

    operations = base_query.all()
    if not operations:
        return RecentStats()

    for op in operations:
        op.created_at = _normalize_dt(op.created_at)

    amounts = [op.amount for op in operations]
    avg_amount = sum(amounts) / len(amounts)
    max_amount = max(amounts)

    ops_last_day = [op for op in operations if op.created_at and op.created_at >= last_day]
    ops_last_hour = [op for op in operations if op.created_at and op.created_at >= last_hour]
    usual_product_types = {op.product_type for op in operations if op.product_type}

    return RecentStats(
        avg_amount=avg_amount,
        max_amount=max_amount,
        operations_count_last_24h=len(ops_last_day),
        operations_count_last_hour=len(ops_last_hour),
        usual_product_types=usual_product_types,
    )


async def evaluate_rules(
    context: "OperationContext",
    db: Session | None = None,
    rules: Iterable[Union[RuleDefinition, RuleConfig]] | None = None,
) -> "RiskResult":
    # Lazy import to avoid circular dependency
    from app.services.risk_adapter import RiskResult

    reasons: list[str] = []
    flags: dict[str, Any] = {}
    level = "LOW"

    now = _normalize_dt(context.created_at) or datetime.now(timezone.utc)
    stats = await load_recent_operations_stats(db, context.card_id, context.client_id, now)

    active_rules = _normalize_rules(rules)

    for rule in active_rules:
        window_ops: Sequence[Operation] = []
        if rule.window:
            window_ops = _load_operations(db, context, rule.window, now)
            if not window_ops and rule.metric in {MetricType.COUNT, MetricType.TOTAL_AMOUNT}:
                # no data available for window-based rules
                window_ops = []

        triggered, match_flags = rule.evaluate(context, stats, window_ops)
        if not triggered:
            continue

        reason = rule.reason or rule.name
        reasons.append(reason)
        flags.setdefault("rules", []).append({"name": rule.name, **match_flags})
        level = _raise_level(level, rule.action.value)

    risk_score = _compute_score(level, reasons)
    return RiskResult(
        risk_score=risk_score,
        risk_result=level,
        reasons=reasons,
        flags=flags,
        source="RULES",
    )

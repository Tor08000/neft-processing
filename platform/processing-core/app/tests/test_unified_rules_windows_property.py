from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from app.schemas.unified_rules import RuleEvaluationContext, RuleEvaluationObject, RuleEvaluationSubject
from app.services.unified_rules_engine import _triggered, _window_bounds, resolve_decision, evaluate_rules
from app.models.unified_rule import UnifiedRule, UnifiedRuleMetric, UnifiedRulePolicy, UnifiedRuleScope
from app.services.unified_rules_engine import SyntheticMetricsProvider


@given(
    timestamp=st.datetimes(timezones=st.just(timezone.utc)),
    minutes=st.integers(min_value=1, max_value=120),
)
def test_rolling_window_includes_boundary(timestamp: datetime, minutes: int) -> None:
    window = {"type": "rolling", "unit": "minute", "size": minutes}
    start, end = _window_bounds(_make_window(window), timestamp)
    assert end == timestamp
    assert start == timestamp - timedelta(minutes=minutes)


@given(timestamp=st.datetimes(timezones=st.just(timezone.utc)))
def test_calendar_window_month_resets(timestamp: datetime) -> None:
    window = {"type": "calendar", "unit": "month", "size": 1}
    start, _ = _window_bounds(_make_window(window), timestamp)
    assert start.day == 1
    assert start.hour == 0
    assert start.minute == 0


@given(
    threshold=st.integers(min_value=1, max_value=10_000),
    delta=st.integers(min_value=0, max_value=10_000),
)
def test_usage_monotonicity_for_limit(threshold: int, delta: int) -> None:
    value_cfg = {"op": "<=", "threshold": threshold}
    smaller = threshold + 1
    larger = smaller + delta
    assert _triggered(_make_value(value_cfg), smaller) is True
    assert _triggered(_make_value(value_cfg), larger) is True


def test_decision_determinism() -> None:
    rule = UnifiedRule(
        code="DETERMINISTIC_RULE",
        version_id=1,
        scope=UnifiedRuleScope.API,
        metric=UnifiedRuleMetric.COUNT,
        window={"type": "rolling", "unit": "minute", "size": 1},
        value={"op": ">=", "threshold": 1},
        policy=UnifiedRulePolicy.SOFT_DECLINE,
        priority=10,
    )
    context = RuleEvaluationContext(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scope=UnifiedRuleScope.API,
        subject=RuleEvaluationSubject(),
        object=RuleEvaluationObject(endpoint="/v1/test"),
    )
    provider = SyntheticMetricsProvider({"COUNT": 1})
    matched = evaluate_rules([rule], context, provider)
    decision_a, _ = resolve_decision(matched)
    decision_b, _ = resolve_decision(matched)
    assert decision_a == decision_b


def _make_window(window: dict) -> object:
    from app.schemas.unified_rules import RuleWindowConfig

    return RuleWindowConfig.model_validate(window)


def _make_value(value: dict) -> object:
    from app.schemas.unified_rules import RuleValueConfig

    return RuleValueConfig.model_validate(value)

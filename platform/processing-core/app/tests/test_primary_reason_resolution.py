from app.models.unified_explain import PrimaryReason
from app.services.explain.unified import resolve_primary_reasons


def test_primary_reason_priority_risk_over_limit() -> None:
    primary, secondary = resolve_primary_reasons({PrimaryReason.LIMIT, PrimaryReason.RISK})

    assert primary == PrimaryReason.RISK
    assert secondary == [PrimaryReason.LIMIT]


def test_primary_reason_priority_limit_over_logistics() -> None:
    primary, secondary = resolve_primary_reasons({PrimaryReason.LOGISTICS, PrimaryReason.LIMIT})

    assert primary == PrimaryReason.LIMIT
    assert secondary == [PrimaryReason.LOGISTICS]


def test_primary_reason_only_money() -> None:
    primary, secondary = resolve_primary_reasons({PrimaryReason.MONEY})

    assert primary == PrimaryReason.MONEY
    assert secondary == []


def test_primary_reason_only_policy() -> None:
    primary, secondary = resolve_primary_reasons({PrimaryReason.POLICY})

    assert primary == PrimaryReason.POLICY
    assert secondary == []


def test_primary_reason_unknown_when_empty() -> None:
    primary, secondary = resolve_primary_reasons(set())

    assert primary == PrimaryReason.UNKNOWN
    assert secondary == []

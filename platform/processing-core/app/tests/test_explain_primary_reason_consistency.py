from app.models.unified_explain import PrimaryReason
from app.services.explain.priority import ensure_primary_reason_consistency
from app.services.explain.unified import resolve_primary_reasons


def test_primary_reason_becomes_unknown_without_limit_section():
    primary = ensure_primary_reason_consistency(PrimaryReason.LIMIT, sections={"risk": {"decision": "BLOCK"}})
    assert primary == PrimaryReason.UNKNOWN


def test_primary_reason_kept_when_logistics_or_navigator_present():
    primary_logistics = ensure_primary_reason_consistency(PrimaryReason.LOGISTICS, sections={"logistics": {"order_id": "1"}})
    assert primary_logistics == PrimaryReason.LOGISTICS

    primary_navigator = ensure_primary_reason_consistency(PrimaryReason.LOGISTICS, sections={"navigator": {"route_snapshot_id": "1"}})
    assert primary_navigator == PrimaryReason.LOGISTICS


def test_secondary_reasons_preserved_when_primary_invalid():
    primary, secondary = resolve_primary_reasons({PrimaryReason.LIMIT, PrimaryReason.RISK})
    assert primary == PrimaryReason.RISK
    assert secondary == [PrimaryReason.LIMIT]

    adjusted = ensure_primary_reason_consistency(primary, sections={"limits": {"limit_value": 1}})
    assert adjusted == PrimaryReason.UNKNOWN
    assert secondary == [PrimaryReason.LIMIT]

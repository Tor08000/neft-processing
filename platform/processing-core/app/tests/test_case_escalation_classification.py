from app.models.cases import Case, CaseKind, CasePriority, CaseQueue, CaseStatus
from app.services.case_escalation_service import classify_case


def _base_case() -> Case:
    return Case(
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        kpi_key=None,
        window_days=None,
        title="Case: operation op-1",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
    )


def test_classify_case_routes_fraud_queue():
    case = _base_case()
    explain = {"reason_codes": ["velocity_high", "geo_mismatch"]}

    result = classify_case(case, explain, None)

    assert result.queue == CaseQueue.FRAUD_OPS
    assert any("velocity" in rule for rule in result.matched_rules)


def test_classify_case_routes_finance_queue():
    case = _base_case()
    explain = {"reason_codes": ["invoice_delay"]}

    result = classify_case(case, explain, None)

    assert result.queue == CaseQueue.FINANCE_OPS


def test_classify_case_routes_support_queue_by_default():
    case = _base_case()
    explain = {"reason_codes": ["unknown_reason"]}

    result = classify_case(case, explain, None)

    assert result.queue == CaseQueue.SUPPORT

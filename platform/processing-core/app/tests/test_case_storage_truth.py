from sqlalchemy import String

from app.models.audit_retention import AuditLegalHold, AuditPurgeLog
from app.models.case_exports import CaseExport
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.decision_memory import DecisionMemoryRecord
from app.models.marketplace_orders import MarketplaceOrderEvent
from app.models.service_bookings import ServiceBookingEvent


def _assert_string36(column) -> None:
    assert isinstance(column.type, String)
    assert column.type.length == 36


def test_cases_and_support_audit_storage_use_string_ids() -> None:
    _assert_string36(Case.__table__.c.id)
    _assert_string36(Case.__table__.c.case_source_ref_id)
    _assert_string36(CaseSnapshot.__table__.c.id)
    _assert_string36(CaseSnapshot.__table__.c.case_id)
    _assert_string36(CaseComment.__table__.c.id)
    _assert_string36(CaseComment.__table__.c.case_id)
    _assert_string36(CaseEvent.__table__.c.id)
    _assert_string36(CaseEvent.__table__.c.case_id)
    _assert_string36(CaseExport.__table__.c.id)
    _assert_string36(CaseExport.__table__.c.case_id)
    _assert_string36(CaseExport.__table__.c.created_by_user_id)
    _assert_string36(AuditLegalHold.__table__.c.id)
    _assert_string36(AuditLegalHold.__table__.c.case_id)
    _assert_string36(AuditLegalHold.__table__.c.created_by)
    _assert_string36(AuditPurgeLog.__table__.c.id)
    _assert_string36(AuditPurgeLog.__table__.c.case_id)


def test_case_event_dependent_storage_uses_string_ids() -> None:
    _assert_string36(DecisionMemoryRecord.__table__.c.id)
    _assert_string36(DecisionMemoryRecord.__table__.c.case_id)
    _assert_string36(DecisionMemoryRecord.__table__.c.decision_ref_id)
    _assert_string36(DecisionMemoryRecord.__table__.c.decided_by_user_id)
    _assert_string36(DecisionMemoryRecord.__table__.c.audit_event_id)
    _assert_string36(MarketplaceOrderEvent.__table__.c.audit_event_id)
    _assert_string36(ServiceBookingEvent.__table__.c.audit_event_id)

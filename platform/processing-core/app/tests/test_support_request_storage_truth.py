from app.models.support_request import SupportRequest


def test_support_request_storage_uses_string_ids_matching_live_schema() -> None:
    assert str(SupportRequest.__table__.c.id.type) == "VARCHAR(36)"
    assert str(SupportRequest.__table__.c.subject_id.type) == "VARCHAR(36)"
    assert str(SupportRequest.__table__.c.event_id.type) == "VARCHAR(36)"

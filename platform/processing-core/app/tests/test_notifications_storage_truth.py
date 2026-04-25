from sqlalchemy import String, Text

from app.models.notifications import (
    NotificationDelivery,
    NotificationMessage,
    NotificationPreference,
    NotificationTemplate,
)


def _assert_string36(column) -> None:
    assert isinstance(column.type, String)
    assert column.type.length == 36


def test_notification_ids_match_live_string_storage() -> None:
    _assert_string36(NotificationTemplate.__table__.c.id)
    _assert_string36(NotificationPreference.__table__.c.id)
    _assert_string36(NotificationMessage.__table__.c.id)
    _assert_string36(NotificationDelivery.__table__.c.id)
    _assert_string36(NotificationDelivery.__table__.c.message_id)


def test_notification_outbox_aggregate_id_matches_live_text_storage() -> None:
    assert isinstance(NotificationMessage.__table__.c.aggregate_id.type, Text)

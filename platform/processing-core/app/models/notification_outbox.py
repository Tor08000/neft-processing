"""Compatibility import for notification outbox ORM model.

Canonical SQLAlchemy mapping for `notification_outbox` lives in
`app.models.notifications.NotificationMessage`.
"""

from app.models.notifications import NotificationMessage

NotificationOutbox = NotificationMessage

__all__ = ["NotificationOutbox"]

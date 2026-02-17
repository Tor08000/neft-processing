from __future__ import annotations

import os

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.domains.client.docflow.notifications import ClientDocflowNotificationsService
from app.domains.client.docflow.packages import ClientDocflowPackagesService
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage


@celery_client.task(name="documents.build_package")
def build_document_package(package_id: str) -> None:
    session = get_sessionmaker()()
    try:
        service = ClientDocflowPackagesService(db=session, storage=OnboardingDocumentsStorage.from_env())
        package = service.build_package(package_id)
        notification = ClientDocflowNotificationsService(db=session).create(
            client_id=str(package.client_id),
            user_id=str(package.created_by_user_id) if package.created_by_user_id else None,
            kind="PACKAGE_READY",
            title="Пакет документов готов",
            message=f"Пакет {package.filename or package.id} готов к скачиванию",
            payload={"package_id": package.id},
            dedupe_key=f"package-ready:{package.id}",
        )
        _dispatch_external_notifications(notification_id=notification.id, title=notification.title, message=notification.message)
    finally:
        session.close()


def _dispatch_external_notifications(*, notification_id: str, title: str, message: str) -> None:
    email_enabled = os.getenv("NOTIFY_EMAIL_ENABLED", "0") == "1"
    telegram_enabled = os.getenv("NOTIFY_TELEGRAM_ENABLED", "0") == "1"
    if not (email_enabled or telegram_enabled):
        return
    # best-effort; integration-hub failures must not break package flow
    try:
        from app.services.integration_hub_client import send_notification

        for channel in ("email", "telegram"):
            if (channel == "email" and not email_enabled) or (channel == "telegram" and not telegram_enabled):
                continue
            send_notification(
                channel=channel,
                destination="",
                template="client_notification",
                data={"title": title, "message": message, "deep_link": "/client/notifications"},
                idempotency_key=f"notif:{notification_id}:{channel}",
            )
    except Exception:
        return

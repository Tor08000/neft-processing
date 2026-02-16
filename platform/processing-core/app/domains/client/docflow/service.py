from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domains.client.docflow.notifications import ClientDocflowNotificationsService
from app.domains.client.docflow.packages import ClientDocflowPackagesService
from app.domains.client.docflow.timeline import ClientDocflowTimelineService
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage


@dataclass(slots=True)
class ClientDocflowService:
    db: Session

    @property
    def timeline(self) -> ClientDocflowTimelineService:
        return ClientDocflowTimelineService(self.db)

    @property
    def packages(self) -> ClientDocflowPackagesService:
        return ClientDocflowPackagesService(self.db, OnboardingDocumentsStorage.from_env())

    @property
    def notifications(self) -> ClientDocflowNotificationsService:
        return ClientDocflowNotificationsService(self.db)

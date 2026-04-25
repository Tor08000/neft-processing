from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.onboarding.models import ClientOnboardingApplication, OnboardingApplicationStatus


@dataclass(slots=True)
class ClientOnboardingRepository:
    db: Session

    def create_draft(self, **kwargs) -> ClientOnboardingApplication:
        obj = ClientOnboardingApplication(id=new_uuid_str(), status=OnboardingApplicationStatus.DRAFT.value, **kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_by_id(self, application_id: str) -> ClientOnboardingApplication | None:
        return self.db.get(ClientOnboardingApplication, application_id)

    def update_draft(self, application: ClientOnboardingApplication, patch: dict[str, object]) -> ClientOnboardingApplication:
        for key, value in patch.items():
            setattr(application, key, value)
        application.updated_at = datetime.now(timezone.utc)
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def set_submitted(self, application: ClientOnboardingApplication) -> ClientOnboardingApplication:
        now = datetime.now(timezone.utc)
        application.status = OnboardingApplicationStatus.SUBMITTED.value
        application.submitted_at = now
        application.updated_at = now
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def find_latest_by_email(self, email: str) -> ClientOnboardingApplication | None:
        stmt = (
            select(ClientOnboardingApplication)
            .where(func.lower(ClientOnboardingApplication.email) == email.lower())
            .order_by(ClientOnboardingApplication.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_latest_approved_by_client_id(self, client_id: str) -> ClientOnboardingApplication | None:
        stmt = (
            select(ClientOnboardingApplication)
            .where(ClientOnboardingApplication.client_id == client_id)
            .where(ClientOnboardingApplication.status == OnboardingApplicationStatus.APPROVED.value)
            .order_by(ClientOnboardingApplication.approved_at.desc(), ClientOnboardingApplication.updated_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

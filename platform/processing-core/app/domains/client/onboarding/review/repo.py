from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from uuid import uuid4
from app.domains.client.onboarding.documents.models import ClientDocument
from app.domains.client.onboarding.models import ClientOnboardingApplication
from app.models.client import Client
from app.models.client_users import ClientUser
from app.models.client_user_roles import ClientUserRole


@dataclass(slots=True)
class OnboardingReviewRepository:
    db: Session

    def list_applications(self, *, status: str | None, q: str | None, limit: int, offset: int) -> list[ClientOnboardingApplication]:
        stmt = select(ClientOnboardingApplication)
        if status:
            stmt = stmt.where(ClientOnboardingApplication.status == status)
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    ClientOnboardingApplication.company_name.ilike(pattern),
                    ClientOnboardingApplication.inn.ilike(pattern),
                    ClientOnboardingApplication.email.ilike(pattern),
                    ClientOnboardingApplication.phone.ilike(pattern),
                )
            )
        stmt = stmt.order_by(ClientOnboardingApplication.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars())

    def get_application(self, application_id: str) -> ClientOnboardingApplication | None:
        return self.db.get(ClientOnboardingApplication, application_id)

    def get_document(self, doc_id: str) -> ClientDocument | None:
        return self.db.get(ClientDocument, doc_id)

    def list_documents(self, application_id: str) -> list[ClientDocument]:
        stmt = (
            select(ClientDocument)
            .where(ClientDocument.client_application_id == application_id)
            .order_by(ClientDocument.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars())

    def save(self, obj):
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_client_by_inn(self, inn: str) -> Client | None:
        stmt = select(Client).where(Client.inn == inn).order_by(Client.created_at.asc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_client(self, *, company_name: str, inn: str, ogrn: str | None) -> Client:
        client = Client(
            id=uuid4(),
            name=company_name,
            legal_name=company_name,
            inn=inn,
            ogrn=ogrn,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
        )
        if ogrn:
            client.external_id = ogrn
        self.db.add(client)
        self.db.flush()
        return client

    def ensure_client_user_membership(self, *, client_id: str, user_id: str, status: str = "ACTIVE") -> ClientUser:
        stmt = select(ClientUser).where(ClientUser.client_id == client_id, ClientUser.user_id == user_id).limit(1)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            existing.status = status
            self.db.add(existing)
            return existing

        item = ClientUser(id=new_uuid_str(), client_id=client_id, user_id=user_id, status=status)
        self.db.add(item)
        return item

    def ensure_client_user_role(self, *, client_id: str, user_id: str, role: str = "CLIENT_OWNER") -> ClientUserRole:
        stmt = select(ClientUserRole).where(ClientUserRole.client_id == client_id, ClientUserRole.user_id == user_id).limit(1)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            current_roles = {item.strip() for item in (existing.roles or "").split(",") if item.strip()}
            current_roles.add(role)
            existing.roles = ",".join(sorted(current_roles))
            self.db.add(existing)
            return existing

        item = ClientUserRole(id=new_uuid_str(), client_id=client_id, user_id=user_id, roles=role)
        self.db.add(item)
        return item

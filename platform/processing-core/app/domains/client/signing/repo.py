from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.signing.models import ClientAuditEvent, ClientDocSignRequest


@dataclass(slots=True)
class ClientSigningRepository:
    db: Session

    def get_pending_request_for_doc(self, doc_id: str) -> ClientDocSignRequest | None:
        stmt = select(ClientDocSignRequest).where(
            and_(ClientDocSignRequest.doc_id == doc_id, ClientDocSignRequest.status == "PENDING")
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_sign_request(
        self,
        *,
        doc_id: str,
        user_id: str,
        phone: str,
        otp_hash: str,
        expires_at: datetime,
        max_attempts: int,
        request_ip: str | None,
        request_user_agent: str | None,
    ) -> ClientDocSignRequest:
        pending = self.get_pending_request_for_doc(doc_id)
        if pending is not None:
            pending.status = "CANCELLED"
            self.db.add(pending)
        obj = ClientDocSignRequest(
            id=new_uuid_str(),
            doc_id=doc_id,
            user_id=user_id,
            phone=phone,
            otp_hash=otp_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
            status="PENDING",
            request_ip=request_ip,
            request_user_agent=request_user_agent,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get_request(self, request_id: str) -> ClientDocSignRequest | None:
        return self.db.get(ClientDocSignRequest, request_id)

    def increment_attempts(self, req: ClientDocSignRequest) -> ClientDocSignRequest:
        req.attempts += 1
        if req.attempts >= req.max_attempts:
            req.status = "CANCELLED"
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def mark_expired(self, req: ClientDocSignRequest) -> ClientDocSignRequest:
        req.status = "EXPIRED"
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def mark_verified(self, req: ClientDocSignRequest) -> ClientDocSignRequest:
        req.status = "VERIFIED"
        req.verified_at = datetime.now(timezone.utc)
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def create_audit_event(
        self,
        *,
        client_id: str | None,
        application_id: str | None,
        doc_id: str | None,
        event_type: str,
        actor_user_id: str | None,
        actor_type: str | None,
        ip: str | None,
        user_agent: str | None,
        meta_json: dict,
    ) -> ClientAuditEvent:
        obj = ClientAuditEvent(
            id=new_uuid_str(),
            client_id=client_id,
            application_id=application_id,
            doc_id=doc_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            ip=ip,
            user_agent=user_agent,
            meta_json=meta_json,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list_audit_by_doc(self, doc_id: str) -> list[ClientAuditEvent]:
        stmt = select(ClientAuditEvent).where(ClientAuditEvent.doc_id == doc_id).order_by(ClientAuditEvent.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

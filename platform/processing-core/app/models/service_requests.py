from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ServiceRequestStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(GUID(), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    service_id = Column(GUID(), nullable=False, index=True)
    status = Column(ExistingEnum(ServiceRequestStatus, name="service_request_status"), nullable=False, default=ServiceRequestStatus.NEW.value)
    payload = Column(JSON_TYPE, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


Index("ix_service_requests_tenant_partner_status", ServiceRequest.tenant_id, ServiceRequest.partner_id, ServiceRequest.status)
Index("ix_service_requests_tenant_client_created", ServiceRequest.tenant_id, ServiceRequest.client_id, ServiceRequest.created_at)


__all__ = ["ServiceRequest", "ServiceRequestStatus"]

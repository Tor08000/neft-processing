from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class ClientLimitChangeRequest(Base):
    __tablename__ = "client_limit_change_requests"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    limit_type = Column(String(128), nullable=False)
    new_value = Column(Numeric, nullable=False)
    comment = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default="PENDING", index=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = ["ClientLimitChangeRequest"]

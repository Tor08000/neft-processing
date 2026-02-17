from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class LimitTemplate(Base):
    __tablename__ = "limit_templates"
    __table_args__ = (UniqueConstraint("client_id", "name", name="uq_limit_templates_client_name"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    limits = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, server_default="ACTIVE")
    is_default = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

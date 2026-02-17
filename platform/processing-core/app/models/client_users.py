from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class ClientUser(Base):
    __tablename__ = "client_users"
    __table_args__ = (UniqueConstraint("client_id", "user_id", name="uq_client_users_client_user"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

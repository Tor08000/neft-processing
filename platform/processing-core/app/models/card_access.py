from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class CardAccessScope(str, Enum):
    VIEW = "VIEW"
    USE = "USE"
    MANAGE = "MANAGE"


class CardAccess(Base):
    __tablename__ = "card_access"
    __table_args__ = (UniqueConstraint("card_id", "user_id", name="uq_card_access_user_card"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    card_id = Column(String, nullable=False, index=True)
    scope = Column(ExistingEnum(CardAccessScope, name="card_access_scope"), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    effective_to = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

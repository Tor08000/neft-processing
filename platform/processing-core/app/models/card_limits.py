from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID, new_uuid_str


class CardLimit(Base):
    __tablename__ = "card_limits"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    card_id = Column(String, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    limit_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

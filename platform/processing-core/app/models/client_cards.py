from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class ClientCard(Base):
    __tablename__ = "client_cards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    card_id = Column(String, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    pan_masked = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

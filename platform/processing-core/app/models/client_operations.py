from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class ClientOperation(Base):
    __tablename__ = "client_operations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    card_id = Column(String, nullable=True, index=True)
    operation_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fuel_type = Column(String, nullable=True)

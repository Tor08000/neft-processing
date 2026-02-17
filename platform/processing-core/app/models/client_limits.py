from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ClientLimit(Base):
    __tablename__ = "client_limits"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )
    limit_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String(3), nullable=False, server_default="RUB")
    used_amount = Column(Numeric, nullable=True, server_default="0")
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)

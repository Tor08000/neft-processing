from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, JSON, String, func

from app.db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor = Column(String, nullable=True)
    action = Column(String, nullable=True)
    target = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    hash = Column(String, nullable=True)


__all__ = ["AuditLog"]

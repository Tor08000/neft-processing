from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text, func

from app.db import Base


class AuditSigningKeyRecord(Base):
    __tablename__ = "audit_signing_keys"

    key_id = Column(String(256), primary_key=True)
    alg = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    public_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["AuditSigningKeyRecord"]

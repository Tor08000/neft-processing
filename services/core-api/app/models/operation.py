# services/core-api/app/models/operation.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class Operation(Base):
    __tablename__ = "operations"

    # Используем operation_id как первичный ключ — он уже есть в JSON-ответах
    operation_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    operation_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)

    merchant_id = Column(String(64), nullable=False)
    terminal_id = Column(String(64), nullable=False)
    client_id = Column(String(64), nullable=False)
    card_id = Column(String(64), nullable=False)

    amount = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False)

    daily_limit = Column(Integer, nullable=True)
    limit_per_tx = Column(Integer, nullable=True)
    used_today = Column(Integer, nullable=True)
    new_used_today = Column(Integer, nullable=True)

    authorized = Column(Boolean, nullable=False, default=False)

    response_code = Column(String(16), nullable=True)
    response_message = Column(String(255), nullable=True)

    parent_operation_id = Column(UUID(as_uuid=True), nullable=True)
    reason = Column(String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Operation(operation_id={self.operation_id}, "
            f"type={self.operation_type}, status={self.status}, amount={self.amount})>"
        )

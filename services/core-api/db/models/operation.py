# services/core-api/app/db/models/operation.py

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Operation(Base):
    """
    Журнал операций терминала / процессинга.

    Соответствует таблице "operations" и миграции 20251118_0002_operations_journal.
    """

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # технический UUID операции (AUTH/CAPTURE/REVERSAL/REFUND)
    operation_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    operation_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    merchant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    terminal_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    client_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    card_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    # авторизована ли операция (для REVERSAL/REFUND тоже сохраняем)
    authorized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    response_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    response_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # лимиты на момент операции
    daily_limit: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    limit_per_tx: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    used_today: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    new_used_today: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # родительская операция (AUTH или CAPTURE)
    parent_operation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

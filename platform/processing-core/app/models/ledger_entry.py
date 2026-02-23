from __future__ import annotations

from enum import Enum
from uuid import UUID as UUIDType

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    func,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db import Base


class LedgerDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntry(Base):
    """Represents a posted ledger movement for an account."""

    __tablename__ = "ledger_entries"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    entry_id: UUIDType = Column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    posting_id: UUIDType | None = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    account_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_id: UUIDType | None = Column(
        PGUUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction = Column(SAEnum(LedgerDirection), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    balance_before = Column(Numeric(18, 4), nullable=True)
    balance_after = Column(Numeric(18, 4), nullable=True)
    posted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    value_date = Column(Date, nullable=True)
    context = Column("metadata", JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr is for debugging
        return f"<LedgerEntry id={self.id} account_id={self.account_id} direction={self.direction}>"


@event.listens_for(LedgerEntry, "before_update", propagate=True)
def _prevent_ledger_entry_update(mapper, connection, target):  # pragma: no cover - guardrail
    raise ValueError("ledger_entries_are_append_only")


@event.listens_for(LedgerEntry, "before_delete", propagate=True)
def _prevent_ledger_entry_delete(mapper, connection, target):  # pragma: no cover - guardrail
    raise ValueError("ledger_entries_are_append_only")

from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)

from app.db import Base


class AccountType(str, Enum):
    CLIENT_MAIN = "CLIENT_MAIN"
    CLIENT_CREDIT = "CLIENT_CREDIT"
    CARD_LIMIT = "CARD_LIMIT"
    TECHNICAL = "TECHNICAL"


class AccountOwnerType(str, Enum):
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    PLATFORM = "PLATFORM"


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class Account(Base):
    """Customer or technical account used for posting ledger entries."""

    __tablename__ = "accounts"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    client_id = Column(String(64), nullable=False, index=True)
    owner_type = Column(SAEnum(AccountOwnerType), nullable=False, index=True, default=AccountOwnerType.CLIENT)
    owner_id = Column(String(64), nullable=False, index=True)
    card_id = Column(String(64), ForeignKey("cards.id"), nullable=True, index=True)
    tariff_id = Column(String(64), nullable=True)
    currency = Column(String(8), nullable=False)
    type = Column(SAEnum(AccountType), nullable=False, index=True)
    status = Column(
        SAEnum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - repr is for debugging
        return f"<Account id={self.id} client={self.client_id} type={self.type}>"


class AccountBalance(Base):
    """Current and available balances for an account."""

    __tablename__ = "account_balances"

    account_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_balance = Column(Numeric(18, 4), nullable=False, default=0)
    available_balance = Column(Numeric(18, 4), nullable=False, default=0)
    hold_balance = Column(Numeric(18, 4), nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - repr is for debugging
        return f"<AccountBalance account_id={self.account_id} balance={self.current_balance}>"

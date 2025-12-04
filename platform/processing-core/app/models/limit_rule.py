from enum import Enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum as SAEnum, Integer, Numeric, String, func

from app.db import Base


class LimitEntityType(str, Enum):
    CLIENT = "CLIENT"
    CARD = "CARD"
    TERMINAL = "TERMINAL"
    MERCHANT = "MERCHANT"


class LimitScope(str, Enum):
    PER_TX = "PER_TX"
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"


class FuelProductType(str, Enum):
    ANY = "ANY"
    DIESEL = "DIESEL"
    AI92 = "AI92"
    AI95 = "AI95"
    AI98 = "AI98"
    GAS = "GAS"
    OTHER = "OTHER"


class LimitRule(Base):
    __tablename__ = "limits_rules"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    phase = Column(String(16), nullable=False, default="AUTH")
    entity_type = Column(SAEnum(LimitEntityType), nullable=False, default=LimitEntityType.CLIENT)
    scope = Column(SAEnum(LimitScope), nullable=False, default=LimitScope.PER_TX)
    product_type = Column(SAEnum(FuelProductType), nullable=True)

    client_id = Column(String(64), nullable=True, index=True)
    card_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(String(64), nullable=True, index=True)
    terminal_id = Column(String(64), nullable=True, index=True)

    client_group_id = Column(String(64), nullable=True, index=True)
    card_group_id = Column(String(64), nullable=True, index=True)

    product_category = Column(String(64), nullable=True, index=True)
    mcc = Column(String(32), nullable=True, index=True)
    tx_type = Column(String(32), nullable=True, index=True)

    currency = Column(String(8), nullable=False, default="RUB")
    max_amount = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    max_quantity = Column(Numeric(18, 3), nullable=True)
    daily_limit = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    limit_per_tx = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


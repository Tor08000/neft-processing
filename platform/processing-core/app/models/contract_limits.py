from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db import Base


class TariffPlan(Base):
    """Represents a financial tariff/plan with customizable parameters."""

    __tablename__ = "tariff_plans"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    params = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TariffPrice(Base):
    """Pricing rules for a tariff plan scoped by product and partner/azs."""

    __tablename__ = "tariff_prices"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    tariff_id = Column(String(64), ForeignKey("tariff_plans.id"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    azs_id = Column(String(64), nullable=True, index=True)
    price_per_liter = Column(Numeric(18, 6), nullable=False)
    cost_price_per_liter = Column(Numeric(18, 6), nullable=True)
    currency = Column(String(3), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=True, index=True)
    valid_to = Column(DateTime(timezone=True), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=100, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LimitConfigScope(str, Enum):
    GLOBAL = "GLOBAL"
    CLIENT = "CLIENT"
    CARD = "CARD"
    TARIFF = "TARIFF"


class LimitType(str, Enum):
    DAILY_VOLUME = "DAILY_VOLUME"
    DAILY_AMOUNT = "DAILY_AMOUNT"
    MONTHLY_AMOUNT = "MONTHLY_AMOUNT"
    CREDIT_LIMIT = "CREDIT_LIMIT"


class LimitWindow(str, Enum):
    PER_TX = "PER_TX"
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"


class LimitConfig(Base):
    """Contractual limits applied per client/card/tariff independent from risk DSL."""

    __tablename__ = "limit_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(SAEnum(LimitConfigScope, name="limitconfigscope"), nullable=False, index=True)
    subject_ref = Column(String(64), nullable=False, index=True)
    limit_type = Column(SAEnum(LimitType), nullable=False, index=True)
    value = Column(BigInteger, nullable=False)
    window = Column(
        SAEnum(LimitWindow, name="limitwindow"),
        nullable=False,
        default=LimitWindow.PER_TX,
        server_default=LimitWindow.PER_TX.value,
    )
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    tariff_plan_id = Column(String(64), ForeignKey("tariff_plans.id"), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<LimitConfig id={self.id} scope={self.scope} subject={self.subject_ref} type={self.limit_type}>"

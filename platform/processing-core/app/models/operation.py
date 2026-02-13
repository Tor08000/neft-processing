from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.types import BigInteger
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import synonym

from app.db import Base
from app.db.types import GUID


json_variant = JSON().with_variant(postgresql.JSONB, "postgresql")


class OperationType(str, Enum):
    AUTH = "AUTH"
    HOLD = "HOLD"
    COMMIT = "COMMIT"
    REVERSE = "REVERSE"
    REFUND = "REFUND"
    DECLINE = "DECLINE"
    # Backwards compatibility values
    CAPTURE = "CAPTURE"
    REVERSAL = "REVERSAL"


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    HELD = "HELD"
    COMPLETED = "COMPLETED"
    REVERSED = "REVERSED"
    REFUNDED = "REFUNDED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    CAPTURED = "CAPTURED"
    OPEN = "OPEN"

    # Aliases kept for backward compatibility with older payloads
    APPROVED = AUTHORIZED
    POSTED = AUTHORIZED
    ERROR = DECLINED


class ProductType(str, Enum):
    DIESEL = "DIESEL"
    AI92 = "AI92"
    AI95 = "AI95"
    AI98 = "AI98"
    GAS = "GAS"
    OTHER = "OTHER"


class RiskResult(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Operation(Base):
    __tablename__ = "operations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )

    # External/idempotency identifier preserved for backwards compatibility
    ext_operation_id = Column("operation_id", String(64), unique=True, nullable=False)
    operation_id = synonym("ext_operation_id")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    operation_type = Column(SAEnum(OperationType), index=True, nullable=False)
    status = Column(SAEnum(OperationStatus), index=True, nullable=False)

    merchant_id = Column(String(64), index=True, nullable=False)
    terminal_id = Column(String(64), index=True, nullable=False)
    fuel_station_id = Column(GUID(), ForeignKey("fuel_stations.id"), nullable=True, index=True)
    client_id = Column(String(64), index=True, nullable=False)
    card_id = Column(String(64), index=True, nullable=False)
    tariff_id = Column(String(64), nullable=True, index=True)
    product_id = Column(String(64), nullable=True)

    amount_original = Column("amount", BigInteger, nullable=False)
    amount = synonym("amount_original")
    amount_settled = Column(BigInteger, nullable=True, default=0)
    currency = Column(String(3), nullable=False, default="RUB")

    product_type = Column(SAEnum(ProductType), nullable=True)
    quantity = Column(Numeric(18, 3), nullable=True)
    unit_price = Column(Numeric(18, 3), nullable=True)

    captured_amount = Column(BigInteger, nullable=False, default=0)
    refunded_amount = Column(BigInteger, nullable=False, default=0)

    daily_limit = Column(BigInteger, nullable=True)
    limit_per_tx = Column(BigInteger, nullable=True)
    used_today = Column(BigInteger, nullable=True)
    new_used_today = Column(BigInteger, nullable=True)
    limit_profile_id = Column(String(64), nullable=True)
    limit_check_result = Column(JSON, nullable=True)

    authorized = Column(Boolean, nullable=False, default=False)

    response_code = Column(String(8), nullable=False, default="00")
    response_message = Column(String(255), nullable=False, default="OK")
    auth_code = Column(String(32), nullable=True)

    parent_operation_id = Column(String(64), nullable=True, index=True)
    reason = Column(String(255), nullable=True)

    mcc = Column(String(8), nullable=True, index=True)
    product_code = Column(String(32), nullable=True)
    product_category = Column(String(32), nullable=True, index=True)
    tx_type = Column(String(16), nullable=True, index=True)

    accounts = Column(json_variant, nullable=True)
    posting_result = Column(json_variant, nullable=True)

    risk_score = Column(Float, nullable=True)
    risk_result = Column(SAEnum(RiskResult), nullable=True)
    risk_payload = Column(JSON, nullable=True)

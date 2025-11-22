# services/core-api/app/models.py
from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True, nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    cards = relationship("Card", back_populates="client", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_clients_name", "name"),
    )

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    pan_masked = Column(String(32), nullable=False)    # ############****1234
    token = Column(String(64), unique=True, nullable=False)  # внутренний токен карты
    limit_daily = Column(Float, default=0.0)           # 0 = без лимита
    limit_monthly = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="cards")

    __table_args__ = (
        Index("ix_cards_client_id", "client_id"),
        Index("ix_cards_token", "token"),
    )

class Azs(Base):
    __tablename__ = "azs"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_azs_code", "code"),
        Index("ix_azs_is_active", "is_active"),
    )

class PriceList(Base):
    __tablename__ = "price_lists"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    fuel_type = Column(String(32), nullable=False)    # AI-92, AI-95, Diesel...
    price = Column(Float, nullable=False)             # базовая цена
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("name", "fuel_type", name="uq_price_name_fuel"),
        Index("ix_price_is_active", "is_active"),
    )

class DiscountRule(Base):
    __tablename__ = "discount_rules"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    priority = Column(Integer, default=100)           # меньше = раньше применится
    # простой DSL в виде строки, например: "client_id=={id} and fuel_type=='AI-95' and hour in [8,9,10]"
    condition = Column(String(512), nullable=False)
    discount_percent = Column(Float, default=0.0)     # 5.0 = -5%
    discount_abs = Column(Float, default=0.0)         # фикс. скидка в валюте
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_rules_priority", "priority"),
        Index("ix_rules_is_active", "is_active"),
    )

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    azs_id = Column(Integer, ForeignKey("azs.id"), nullable=False)
    fuel_type = Column(String(32), nullable=False)
    amount = Column(Float, nullable=False)            # литры
    unit_price = Column(Float, nullable=False)        # цена за литр до скидки
    discount_applied = Column(Float, default=0.0)     # абсолютная скидка
    total = Column(Float, nullable=False)             # сумма к оплате (после скидок)
    status = Column(String(32), default="approved")   # pending/approved/declined/reversed
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tx_created_at", "created_at"),
        Index("ix_tx_card", "card_id"),
        Index("ix_tx_status", "status"),
    )


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

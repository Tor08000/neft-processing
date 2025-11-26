from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db import Base


class LimitRule(Base):
    __tablename__ = "limits_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phase = Column(String(16), nullable=False, default="AUTH")

    client_id = Column(String(64), nullable=True, index=True)
    card_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(String(64), nullable=True, index=True)
    terminal_id = Column(String(64), nullable=True, index=True)

    client_group_id = Column(String(64), nullable=True, index=True)
    card_group_id = Column(String(64), nullable=True, index=True)

    product_category = Column(String(64), nullable=True, index=True)
    mcc = Column(String(64), nullable=True, index=True)
    tx_type = Column(String(64), nullable=True, index=True)

    currency = Column(String(8), nullable=False, default="RUB")
    daily_limit = Column(Integer, nullable=True)
    limit_per_tx = Column(Integer, nullable=True)

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

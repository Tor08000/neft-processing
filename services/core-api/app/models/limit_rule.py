from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, func

from app.db import Base


class LimitRule(Base):
    __tablename__ = "limits_rules"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    phase = Column(String(16), nullable=False, default="AUTH")

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
    daily_limit = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    limit_per_tx = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


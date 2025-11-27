from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from app.db import Base


class Operation(Base):
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Внешний UUID операции, который генерируется в main.py
    operation_id = Column(String(64), unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # AUTH / CAPTURE / REFUND / REVERSAL
    operation_type = Column(String(16), index=True, nullable=False)

    # AUTHORIZED / DECLINED / CAPTURED / REFUNDED / REVERSED / etc.
    status = Column(String(32), index=True, nullable=False)

    merchant_id = Column(String(64), index=True, nullable=False)
    terminal_id = Column(String(64), index=True, nullable=False)
    client_id = Column(String(64), index=True, nullable=False)
    card_id = Column(String(64), index=True, nullable=False)

    amount = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="RUB")

    # Лимиты – могут быть NULL для REFUND/REVERSAL
    daily_limit = Column(Integer, nullable=True)
    limit_per_tx = Column(Integer, nullable=True)
    used_today = Column(Integer, nullable=True)
    new_used_today = Column(Integer, nullable=True)

    authorized = Column(Boolean, nullable=False, default=False)

    response_code = Column(String(8), nullable=False, default="00")
    response_message = Column(String(255), nullable=False, default="OK")

    # Связь с родительской операцией (AUTH для CAPTURE, CAPTURE для REFUND, любая для REVERSAL)
    parent_operation_id = Column(String(64), nullable=True, index=True)

    # Причина (для REFUND / REVERSAL)
    reason = Column(String(255), nullable=True)

    # Дополнительные атрибуты транзакции
    mcc = Column(String(8), nullable=True, index=True)
    product_code = Column(String(32), nullable=True)
    product_category = Column(String(32), nullable=True, index=True)
    tx_type = Column(String(16), nullable=True, index=True)

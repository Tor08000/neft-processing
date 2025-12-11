import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Человекочитаемое имя клиента (компания/физлицо)
    name = Column(String, nullable=False)

    # Внешний идентификатор (например, ID в твоей CRM или код клиента)
    external_id = Column(String, nullable=True, unique=True)

    # Регистрационные данные клиента
    inn = Column(String, nullable=True)

    # Контактные данные для клиентского портала
    email = Column(String, nullable=True, unique=True)
    full_name = Column(String, nullable=True)

    # Базовая информация по тарифу и контактному менеджеру
    tariff_plan = Column(String, nullable=True)
    account_manager = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")

    # Когда клиент был создан
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

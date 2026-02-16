import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import GUID


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Человекочитаемое имя клиента (компания/физлицо)
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)

    # Внешний идентификатор (например, ID в твоей CRM или код клиента)
    external_id = Column(String, nullable=True, unique=True)

    # Регистрационные данные клиента
    inn = Column(String, nullable=True)
    ogrn = Column(String, nullable=True)
    org_type = Column(String, nullable=True)

    # Контактные данные для клиентского портала
    email = Column(String, nullable=True, unique=True)
    full_name = Column(String, nullable=True)

    # Базовая информация по тарифу и контактному менеджеру
    tariff_plan = Column(String, nullable=True)
    account_manager = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")
    client_offline_profile_id = Column(GUID(), ForeignKey("fleet_offline_profiles.id"), nullable=True)

    # Когда клиент был создан
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

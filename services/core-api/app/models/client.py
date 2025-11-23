from uuid import uuid4

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # Человекочитаемое имя клиента (компания/физлицо)
    name = Column(String, nullable=False)

    # Внешний идентификатор (например, ID в твоей CRM или код клиента)
    external_id = Column(String, nullable=True, unique=True)

    # Когда клиент был создан
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

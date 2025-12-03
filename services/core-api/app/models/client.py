from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.sql import func

from app.db import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Человекочитаемое имя клиента (компания/физлицо)
    name = Column(String, nullable=False)

    # Внешний идентификатор (например, ID в твоей CRM или код клиента)
    external_id = Column(String, nullable=True, unique=True)

    # Контактные данные для клиентского портала
    email = Column(String, nullable=True, unique=True)
    full_name = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")

    # Когда клиент был создан
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

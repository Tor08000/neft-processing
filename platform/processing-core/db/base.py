# services/core-api/app/db/base.py

from sqlalchemy.orm import DeclarativeBase

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    pass


# ВАЖНО:
# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
# и были доступны для Alembic/создания схемы.
# Здесь НЕТ префикса "app.", только "db.models"
# потому что пакет db — верхнеуровневый (лежит в /app/db).

from db.models.client import Client  # noqa: F401
from db.models.user import User  # noqa: F401
from db.models.operation import Operation  # noqa: F401

__all__ = ["Base", "Client", "User", "Operation"]

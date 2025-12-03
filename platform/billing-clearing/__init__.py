# services/workers/__init__.py
# Оставляем тонкий импорт, чтобы можно было обратиться к приложению из пакета.
from .app.celery_app import celery_app  # noqa: F401

"""Совместимый модуль запуска Celery.

Экспортирует уже сконфигурированный :data:`celery_app` из ``celery_app.py``
для обратной совместимости со старыми путями ``app.main``.
"""

from .celery_app import celery_app

celery = celery_app

__all__ = ["celery", "celery_app"]

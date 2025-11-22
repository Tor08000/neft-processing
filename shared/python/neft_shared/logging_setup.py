"""
Единая настройка логирования для всех сервисов НЕФТЬ.

Использование:
    from neft_shared.logging_setup import init_logging, get_logger

    init_logging()  # один раз при старте сервиса
    logger = get_logger(__name__)
    logger.info("message", extra={"key": "value"})

Особенности:
- JSON-формат для всех логов
- поле "service" берётся из переменной окружения SERVICE_NAME
  (например, SERVICE_NAME=core-api / auth-host / ai-service / workers)
- параметр service_name в init_logging(service_name=...) просто записывает
  значение в SERVICE_NAME, чтобы совместить поведение с существующим кодом Celery.
"""

import json
import logging
import os
from logging import StreamHandler, Formatter
from typing import Optional


def _json_formatter(record: logging.LogRecord) -> str:
    payload = {
        "level": record.levelname,
        "name": record.name,
        "msg": record.getMessage(),
        "time": getattr(record, "asctime", None),
        "module": record.module,
        "func": record.funcName,
        "line": record.lineno,
        "service": os.getenv("SERVICE_NAME", "neft"),
    }
    # если extra добавляли dict-ом
    if hasattr(record, "extra") and isinstance(record.extra, dict):
        payload.update(record.extra)
    return json.dumps(payload, ensure_ascii=False)


class _JsonStreamHandler(StreamHandler):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        # Здесь специально не вызываем logging.Formatter.format,
        # просто превращаем запись в JSON
        return _json_formatter(record)


def init_logging(
    default_level: str | int = "INFO",
    force: bool = True,
    service_name: Optional[str] = None,
) -> None:
    """
    Инициализация логирования.

    :param default_level: Уровень логирования по умолчанию.
    :param force: Если True — переопределяем существующую конфигурацию logging.basicConfig.
    :param service_name: Необязательное имя сервиса.
                         Если передано — пишем его в переменную окружения SERVICE_NAME,
                         чтобы _json_formatter подхватывал.
    """
    if service_name:
        os.environ["SERVICE_NAME"] = service_name

    # basicConfig нужен только чтобы подключить наш StreamHandler,
    # форматером будет заниматься _JsonStreamHandler
    logging.basicConfig(level=default_level, force=force)

    root = logging.getLogger()

    # чистим все старые handlers, чтобы не было дублей
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = _JsonStreamHandler()
    # Formatter обязателен, иначе logging попытается работать с None
    handler.setFormatter(Formatter())
    root.addHandler(handler)

    root.setLevel(default_level)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Унифицированная точка получения логгера.
    """
    return logging.getLogger(name)

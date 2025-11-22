"""Unified JSON logging setup shared across all services."""

from __future__ import annotations

import json
import logging
import os
from logging import Formatter, StreamHandler
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
    if hasattr(record, "extra") and isinstance(record.extra, dict):
        payload.update(record.extra)
    return json.dumps(payload, ensure_ascii=False)


class _JsonStreamHandler(StreamHandler):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        return _json_formatter(record)


def init_logging(
    default_level: str | int = "INFO",
    force: bool = True,
    service_name: Optional[str] = None,
) -> None:
    """Configure root logger to emit JSON to stdout.

    Args:
        default_level: Logging level to apply to the root logger.
        force: Whether to override any existing logging configuration.
        service_name: Optional service name to inject into SERVICE_NAME env var.
    """

    if service_name:
        os.environ["SERVICE_NAME"] = service_name

    logging.basicConfig(level=default_level, force=force)
    root = logging.getLogger()

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = _JsonStreamHandler()
    handler.setFormatter(Formatter())
    root.addHandler(handler)
    root.setLevel(default_level)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger instance."""

    return logging.getLogger(name)


__all__ = ["init_logging", "get_logger"]

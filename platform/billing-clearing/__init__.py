"""Package entrypoint for billing-clearing workers."""

import sys

try:
    from .app.celery_app import celery_app  # noqa: F401
except ImportError:  # pragma: no cover - pytest may import this file as a top-level module
    try:
        from app.celery_app import celery_app  # noqa: F401
    except ImportError:
        if "pytest" not in sys.modules:
            raise
        celery_app = None

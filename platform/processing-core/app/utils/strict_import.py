from __future__ import annotations

import importlib
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def import_router(module_path: str, attr: str = "router", *, mandatory: bool = False) -> Any | None:
    """Import router attribute with strict env-aware behavior.

    In PROD: any import error raises immediately (fail-fast).
    In DEV: optional modules log warning and return None.
    Mandatory modules fail in every environment.
    """

    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except Exception as exc:  # noqa: BLE001
        app_env = settings.APP_ENV.lower()
        if mandatory or app_env == "prod":
            logger.critical(
                "Mandatory module missing in %s: %s (%s)",
                app_env.upper(),
                module_path,
                str(exc),
            )
            raise

        logger.warning(
            "Optional module skipped in DEV: %s (%s)",
            module_path,
            str(exc),
        )
        return None

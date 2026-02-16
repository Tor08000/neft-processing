from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    pass


def run_with_retry(func: Callable[[], object], max_attempts: int = 3, backoff: tuple[float, ...] = (0.3, 0.8, 1.6)) -> object:
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return func()
        except RetryableError as exc:
            last_error = exc
            logger.warning("retryable provider failure", extra={"attempt": attempt, "max_attempts": max_attempts})
            if attempt >= max_attempts:
                break
            time.sleep(backoff[min(attempt - 1, len(backoff) - 1)])
    logger.error("retry attempts exhausted", extra={"max_attempts": max_attempts})
    if last_error is not None:
        raise last_error
    raise RuntimeError("retry_exhausted")

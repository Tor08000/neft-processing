from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error as url_error
from urllib import request

from neft_shared.settings import get_settings

logger = logging.getLogger(__name__)

RATE_WINDOW = timedelta(minutes=1)
CHAT_COOLDOWN_SECONDS = 1


@dataclass(frozen=True)
class TelegramSendResult:
    status_code: int
    body: str | None
    message_id: str | None = None


class TelegramSendError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        retry_after: int | None = None,
        is_permanent: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.retry_after = retry_after
        self.is_permanent = is_permanent


_rate_timestamps: deque[datetime] = deque()
_last_chat_sent: dict[int, datetime] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rate_limit_check() -> int | None:
    settings = get_settings()
    limit = max(1, settings.TELEGRAM_MESSAGE_RATE_LIMIT_PER_MIN)
    now = _now()
    while _rate_timestamps and now - _rate_timestamps[0] > RATE_WINDOW:
        _rate_timestamps.popleft()
    if len(_rate_timestamps) >= limit:
        retry_after = int((RATE_WINDOW - (now - _rate_timestamps[0])).total_seconds())
        return max(retry_after, 1)
    return None


def _chat_cooldown_check(chat_id: int) -> int | None:
    now = _now()
    last_sent = _last_chat_sent.get(chat_id)
    if last_sent and (now - last_sent).total_seconds() < CHAT_COOLDOWN_SECONDS:
        remaining = CHAT_COOLDOWN_SECONDS - (now - last_sent).total_seconds()
        return max(1, int(remaining))
    return None


def _mark_sent(chat_id: int) -> None:
    now = _now()
    _rate_timestamps.append(now)
    _last_chat_sent[chat_id] = now


def _parse_retry_after(body: str | None) -> int | None:
    if not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    params = payload.get("parameters") if isinstance(payload, dict) else None
    if isinstance(params, dict) and isinstance(params.get("retry_after"), int):
        return params["retry_after"]
    return None


def send_message(
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
) -> TelegramSendResult:
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramSendError("telegram_token_missing", is_permanent=True)

    retry_after = _rate_limit_check()
    if retry_after:
        raise TelegramSendError("telegram_rate_limited", status_code=429, retry_after=retry_after)

    chat_retry = _chat_cooldown_check(chat_id)
    if chat_retry:
        raise TelegramSendError("telegram_chat_cooldown", status_code=429, retry_after=chat_retry)

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    body = json.dumps(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            _mark_sent(chat_id)
            message_id = None
            try:
                payload_json = json.loads(response_body)
                if isinstance(payload_json, dict):
                    result = payload_json.get("result")
                    if isinstance(result, dict) and result.get("message_id") is not None:
                        message_id = str(result.get("message_id"))
            except json.JSONDecodeError:
                logger.debug("telegram response not json")
            return TelegramSendResult(status_code=response.status, body=response_body[:500], message_id=message_id)
    except url_error.HTTPError as exc:
        body_text = exc.read().decode("utf-8")[:500] if exc.fp else None
        retry_after = _parse_retry_after(body_text)
        status_code = exc.code
        if status_code in {400, 403}:
            raise TelegramSendError(
                "telegram_permanent_failure",
                status_code=status_code,
                body=body_text,
                is_permanent=True,
            )
        raise TelegramSendError(
            "telegram_send_failed",
            status_code=status_code,
            body=body_text,
            retry_after=retry_after,
        )
    except url_error.URLError as exc:
        raise TelegramSendError("telegram_network_error", body=str(exc.reason)[:200])


__all__ = ["TelegramSendError", "TelegramSendResult", "send_message"]

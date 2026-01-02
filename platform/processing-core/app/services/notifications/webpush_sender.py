from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pywebpush import WebPushException, webpush


@dataclass(frozen=True)
class WebPushResponse:
    status_code: int
    body: str | None


def build_webpush_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


class WebPushSender:
    def __init__(self) -> None:
        self.public_key = os.getenv("WEBPUSH_VAPID_PUBLIC_KEY", "")
        self.private_key = os.getenv("WEBPUSH_VAPID_PRIVATE_KEY", "")
        self.subject = os.getenv("WEBPUSH_SUBJECT", "mailto:notifications@neft.local")

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> WebPushResponse:
        if not self.private_key:
            raise RuntimeError("webpush_private_key_missing")
        data = build_webpush_payload(payload)
        try:
            response = webpush(
                subscription_info=subscription,
                data=data,
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},
            )
            return WebPushResponse(status_code=response.status_code, body=response.text)
        except WebPushException as exc:  # pragma: no cover - passthrough
            response = exc.response
            if response is None:
                raise
            return WebPushResponse(status_code=response.status_code, body=response.text)


__all__ = ["WebPushResponse", "WebPushSender", "build_webpush_payload"]

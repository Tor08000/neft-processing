from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class DeliveryPayload:
    filename: str
    payload: bytes
    content_type: str


@dataclass(frozen=True)
class DeliveryResult:
    delivered_at: datetime
    target: str
    files: tuple[str, ...]


class DeliveryAdapter(ABC):
    @abstractmethod
    def deliver(self, *, payloads: Iterable[DeliveryPayload]) -> DeliveryResult:
        raise NotImplementedError


def build_delivery_result(target: str, payloads: Iterable[DeliveryPayload]) -> DeliveryResult:
    return DeliveryResult(
        delivered_at=datetime.now(timezone.utc),
        target=target,
        files=tuple(payload.filename for payload in payloads),
    )


__all__ = ["DeliveryAdapter", "DeliveryPayload", "DeliveryResult", "build_delivery_result"]

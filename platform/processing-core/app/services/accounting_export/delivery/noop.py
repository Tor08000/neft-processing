from __future__ import annotations

import logging
from typing import Iterable

from app.services.accounting_export.delivery.base import DeliveryAdapter, DeliveryPayload, DeliveryResult, build_delivery_result


logger = logging.getLogger(__name__)


class NoopDeliveryAdapter(DeliveryAdapter):
    def deliver(self, *, payloads: Iterable[DeliveryPayload]) -> DeliveryResult:
        payloads = tuple(payloads)
        logger.info("noop_delivery_adapter_used", extra={"files": [payload.filename for payload in payloads]})
        return build_delivery_result(target="noop://local", payloads=payloads)


__all__ = ["NoopDeliveryAdapter"]

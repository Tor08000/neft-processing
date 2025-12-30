from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    occurred_at: str
    correlation_id: str
    trace_id: str
    schema_version: str
    event_type: str
    payload: dict


def build_event(*, event_type: str, payload: dict, correlation_id: str, trace_id: str | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id=str(uuid4()),
        occurred_at=datetime.now(timezone.utc).isoformat(),
        correlation_id=correlation_id,
        trace_id=trace_id or correlation_id,
        schema_version="1.0",
        event_type=event_type,
        payload=payload,
    )


def publish_event(event: EventEnvelope) -> None:
    logger.info("edo.event", extra={"event": json.dumps(asdict(event), ensure_ascii=False)})


__all__ = ["EventEnvelope", "build_event", "publish_event"]

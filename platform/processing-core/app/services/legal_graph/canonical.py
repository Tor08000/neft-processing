from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime):
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    return value


def canonical_json(data: Any) -> str:
    normalized = _normalize_value(data)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_snapshot(data: Any) -> str:
    payload = canonical_json(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["canonical_json", "hash_snapshot"]

from __future__ import annotations

import json
import math
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
            resolved = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return resolved.astimezone(timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {str(key): _normalize_value(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_value(item) for item in sorted(value, key=lambda item: str(item))]
    return value


def canonical_json(value: Any) -> str:
    normalized = _normalize_value(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def strip_redaction_hash(value: Any) -> Any:
    if isinstance(value, list):
        return [strip_redaction_hash(item) for item in value]
    if isinstance(value, dict):
        if value.get("redacted") is True:
            return {key: item for key, item in value.items() if key != "hash"}
        return {key: strip_redaction_hash(item) for key, item in value.items()}
    return value


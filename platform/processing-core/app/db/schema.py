from __future__ import annotations

import logging
import os
from typing import NamedTuple, cast


DEFAULT_SCHEMA = "public"
PRIMARY_ENV = "NEFT_DB_SCHEMA"
LEGACY_ENV = "DB_SCHEMA"


class SchemaResolution(NamedTuple):
    schema: str
    source: str
    search_path: str

    def line(self) -> str:
        return schema_resolution_line(self.schema, self.source)


def _normalize_schema(schema: str) -> str:
    return schema.strip() or DEFAULT_SCHEMA


def _make_search_path(schema: str) -> str:
    normalized = _normalize_schema(schema)
    if normalized == DEFAULT_SCHEMA:
        return DEFAULT_SCHEMA
    return f"{normalized},public"


def resolve_db_schema(env: os._Environ[str] | None = None) -> SchemaResolution:
    """Resolve the target DB schema and record its source."""

    env_map = cast(os._Environ[str], env or os.environ)

    for key in (PRIMARY_ENV, LEGACY_ENV):
        value = env_map.get(key)
        if value:
            schema = _normalize_schema(value)
            return SchemaResolution(schema=schema, source=key, search_path=_make_search_path(schema))

    return SchemaResolution(schema=DEFAULT_SCHEMA, source="default", search_path=_make_search_path(DEFAULT_SCHEMA))


def schema_resolution_line(schema: str, source: str) -> str:
    return f"schema_resolved={schema} source={source}"


def log_schema_resolution(resolution: SchemaResolution | None = None, *, logger: logging.Logger | None = None) -> None:
    resolved = resolution or resolve_db_schema()
    emitter = (logger or logging.getLogger(__name__)).info
    emitter(resolved.line())


SCHEMA_RESOLUTION = resolve_db_schema()
DB_SCHEMA = SCHEMA_RESOLUTION.schema
DB_SCHEMA_SOURCE = SCHEMA_RESOLUTION.source
DB_SCHEMA_SEARCH_PATH = SCHEMA_RESOLUTION.search_path

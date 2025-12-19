from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Mapping, cast


DEFAULT_SCHEMA = "public"
PRIMARY_ENV = "NEFT_DB_SCHEMA"
LEGACY_ENV = "DB_SCHEMA"


def _normalize_schema(schema: str) -> str:
    return schema.strip() or DEFAULT_SCHEMA


def _quote_schema(schema: str) -> str:
    escaped = schema.replace('"', '""')
    return f'"{escaped}"'


def _make_search_path(schema: str) -> str:
    normalized = _normalize_schema(schema)
    if normalized == DEFAULT_SCHEMA:
        return DEFAULT_SCHEMA
    return f"{normalized},public"


@dataclass(frozen=True)
class SchemaResolution:
    target_schema: str
    source: str
    search_path: str
    quoted_schema: str

    @property
    def search_path_sql(self) -> str:
        return f"SET search_path TO {self.quoted_schema}, public"

    def line(self) -> str:
        return schema_resolution_line(self.target_schema, self.source)


def resolve_db_schema(env: Mapping[str, str] | None = None) -> SchemaResolution:
    """Resolve the target DB schema and record its source."""

    env_map = cast(Mapping[str, str], env or os.environ)

    for key in (PRIMARY_ENV, LEGACY_ENV):
        value = env_map.get(key)
        if value:
            schema = _normalize_schema(value)
            return SchemaResolution(
                target_schema=schema,
                source=key,
                search_path=_make_search_path(schema),
                quoted_schema=_quote_schema(schema),
            )

    return SchemaResolution(
        target_schema=DEFAULT_SCHEMA,
        source="default",
        search_path=_make_search_path(DEFAULT_SCHEMA),
        quoted_schema=_quote_schema(DEFAULT_SCHEMA),
    )


def schema_resolution_line(schema: str, source: str) -> str:
    return f"schema_resolved={schema} source={source}"


def override_schema(schema: str, *, source: str = "override") -> SchemaResolution:
    normalized = _normalize_schema(schema)
    return SchemaResolution(
        target_schema=normalized,
        source=source,
        search_path=_make_search_path(normalized),
        quoted_schema=_quote_schema(normalized),
    )


def log_schema_resolution(resolution: SchemaResolution | None = None, *, logger: logging.Logger | None = None) -> None:
    resolved = resolution or resolve_db_schema()
    emitter = (logger or logging.getLogger(__name__)).info
    emitter(resolved.line())


SCHEMA_RESOLUTION = resolve_db_schema()
DB_SCHEMA = SCHEMA_RESOLUTION.target_schema
DB_SCHEMA_SOURCE = SCHEMA_RESOLUTION.source
DB_SCHEMA_SEARCH_PATH = SCHEMA_RESOLUTION.search_path

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, cast


DEFAULT_SCHEMA = "processing_core"
PRIMARY_ENV = "NEFT_DB_SCHEMA"


def _normalize_schema(schema: str) -> str:
    return schema.strip() or DEFAULT_SCHEMA


def _quote_schema(schema: str) -> str:
    escaped = schema.replace('"', '""')
    return f'"{escaped}"'


def quote_schema(schema: str) -> str:
    return _quote_schema(schema)


@dataclass(frozen=True)
class SchemaResolution:
    schema: str

    @property
    def search_path_sql(self) -> str:
        return f"SET search_path TO {_quote_schema(self.schema)}"

    def line(self) -> str:
        return f"schema_resolved={self.schema}"


def resolve_db_schema(env: Mapping[str, str] | None = None) -> SchemaResolution:
    """Resolve the target DB schema from environment."""

    env_map = cast(Mapping[str, str], env or os.environ)
    schema = _normalize_schema(env_map.get(PRIMARY_ENV, DEFAULT_SCHEMA))
    return SchemaResolution(schema=schema)


def override_schema(schema: str) -> SchemaResolution:
    normalized = _normalize_schema(schema)
    return SchemaResolution(schema=normalized)


def schema_resolution_line(schema: str) -> str:
    return f"schema_resolved={schema}"


SCHEMA_RESOLUTION = resolve_db_schema()
DB_SCHEMA = SCHEMA_RESOLUTION.schema

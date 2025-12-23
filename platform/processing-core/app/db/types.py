from __future__ import annotations

import uuid
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator

from app.db.schema import DB_SCHEMA


class GUID(TypeDecorator[str]):
    """Platform-wide GUID/UUID type with cross-dialect compatibility.

    * PostgreSQL: native UUID with ``as_uuid=True`` for stricter typing.
    * SQLite: stores as ``VARCHAR(36)``.
    * Python side: always returns ``str``.
    """

    impl = sa.String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(sa.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        uuid_value = self._coerce_uuid(value)

        if dialect.name == "postgresql":
            return uuid_value
        return str(uuid_value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        if isinstance(value, uuid.UUID):
            return str(value)

        return str(self._coerce_uuid(value))

    @staticmethod
    def _coerce_uuid(value: object) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid UUID value: {value!r}") from exc

    @property
    def python_type(self):
        return str


def new_uuid_str() -> str:
    return str(uuid.uuid4())


class ExistingEnum(TypeDecorator):
    """Reuses pre-existing PostgreSQL ENUM types without auto-creating them.

    * PostgreSQL: binds to ``postgresql.ENUM(create_type=False)`` so DDL never
      attempts to create the type (it must be provisioned via migration).
    * Other dialects: falls back to a ``sa.Enum`` with ``native_enum=False`` to
      keep SQLite test environments working without native ENUM support.
    """

    impl = sa.String()
    cache_ok = True

    def __init__(self, enum_class: type[Enum], *, name: str, schema: str | None = None):
        self.enum_class = enum_class
        self.name = name
        self.schema = schema or DB_SCHEMA
        self._values = tuple(member.value for member in enum_class)

        self._postgres_impl = postgresql.ENUM(
            *self._values,
            name=self.name,
            schema=self.schema,
            create_type=False,
        )
        self._fallback_impl = sa.Enum(*self._values, name=self.name, native_enum=False)
        super().__init__()

    def load_dialect_impl(self, dialect):  # noqa: D401 - SQLAlchemy hook
        if dialect.name == "postgresql":
            return dialect.type_descriptor(self._postgres_impl)
        return dialect.type_descriptor(self._fallback_impl)

    def process_bind_param(self, value, dialect):  # noqa: D401 - SQLAlchemy hook
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        return str(value)

    def process_result_value(self, value, dialect):  # noqa: D401 - SQLAlchemy hook
        if value is None:
            return None
        return self.enum_class(value)

    @property
    def python_type(self):
        return self.enum_class


__all__ = ["ExistingEnum", "GUID", "new_uuid_str"]

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator


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


__all__ = ["GUID", "new_uuid_str"]

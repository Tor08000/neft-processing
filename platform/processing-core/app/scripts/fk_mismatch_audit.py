from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.append(str(APP_ROOT))
sys.path.append(str(REPO_ROOT / "shared" / "python"))

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.db.types import GUID  # noqa: E402


@dataclass(frozen=True)
class FkMismatch:
    source_table: str
    source_column: str
    source_type: str
    target_table: str
    target_column: str
    target_type: str

    def render(self) -> str:
        return (
            f"{self.source_table}.{self.source_column} ({self.source_type}) -> "
            f"{self.target_table}.{self.target_column} ({self.target_type})"
        )


def _bootstrap_metadata() -> sa.MetaData:
    import importlib
    import pkgutil

    from app.db import Base
    import app.models
    import app.integrations.fuel.models  # noqa: F401

    models_path = APP_ROOT / "app" / "models"
    for module in pkgutil.walk_packages([str(models_path)], prefix="app.models."):
        importlib.import_module(module.name)

    return Base.metadata


def _is_uuid_type(type_: sa.types.TypeEngine) -> bool:
    if isinstance(type_, GUID):
        return True
    if isinstance(type_, postgresql.UUID):
        return True
    sa_uuid = getattr(sa, "UUID", None)
    if sa_uuid is not None and isinstance(type_, sa_uuid):
        return True
    if type_.__class__.__name__.lower() in {"uuid", "pguuid"}:
        return True
    return False


def _is_string_type(type_: sa.types.TypeEngine) -> bool:
    return isinstance(type_, (sa.String, sa.Text, sa.CHAR, sa.VARCHAR))


def _type_label(type_: sa.types.TypeEngine) -> str:
    if _is_uuid_type(type_):
        return "UUID"
    if _is_string_type(type_):
        length = getattr(type_, "length", None)
        if length:
            return f"VARCHAR({length})"
        return "VARCHAR"
    return type_.__class__.__name__


def _find_mismatches(metadata: sa.MetaData) -> list[FkMismatch]:
    mismatches: list[FkMismatch] = []
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            source = fk.parent
            target = fk.column
            source_is_uuid = _is_uuid_type(source.type)
            source_is_string = _is_string_type(source.type)
            target_is_uuid = _is_uuid_type(target.type)
            target_is_string = _is_string_type(target.type)
            if source_is_uuid == target_is_uuid:
                continue
            if source_is_string == target_is_string:
                continue
            mismatches.append(
                FkMismatch(
                    source_table=table.name,
                    source_column=source.name,
                    source_type=_type_label(source.type),
                    target_table=target.table.name,
                    target_column=target.name,
                    target_type=_type_label(target.type),
                )
            )
    return sorted(
        mismatches,
        key=lambda item: (
            item.source_table,
            item.source_column,
            item.target_table,
            item.target_column,
        ),
    )


def main() -> None:
    metadata = _bootstrap_metadata()
    mismatches = _find_mismatches(metadata)
    if not mismatches:
        print("No FK type mismatches found.")
        return
    print("FK type mismatches:")
    for mismatch in mismatches:
        print(f"- {mismatch.render()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MIGRATION_ROOT = PROJECT_ROOT / "platform"
MODEL_ROOT = PROJECT_ROOT / "platform" / "processing-core" / "app" / "models"


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str


FORBIDDEN_HINT = (
    "Use ensure_pg_enum/ensure_pg_enum_value for DDL and "
    "postgresql.ENUM(..., create_type=False, schema=SCHEMA) for models/migrations."
)


def iter_migration_files() -> Iterable[Path]:
    if not MIGRATION_ROOT.exists():
        return []
    return MIGRATION_ROOT.rglob("alembic/versions/*.py")


def iter_model_files() -> Iterable[Path]:
    if not MODEL_ROOT.exists():
        return []
    return MODEL_ROOT.rglob("*.py")


def is_postgresql_enum(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "ENUM"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "postgresql"
    )


def is_sa_enum(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "Enum"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "sa"
    )


def is_op_execute(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "execute"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "op"
    )


def extract_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "text":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                return node.args[0].value
        if isinstance(node.func, ast.Name) and node.func.id == "text":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                return node.args[0].value
    return None


def keyword_map(call: ast.Call) -> dict[str, ast.keyword]:
    return {kw.arg: kw for kw in call.keywords if kw.arg}


def check_postgresql_enum(path: Path, call: ast.Call) -> list[Violation]:
    violations: list[Violation] = []
    keywords = keyword_map(call)

    create_type_kw = keywords.get("create_type")
    if create_type_kw is None or not (
        isinstance(create_type_kw.value, ast.Constant) and create_type_kw.value.value is False
    ):
        violations.append(
            Violation(
                path,
                call.lineno,
                "postgresql.ENUM must set create_type=False.",
            )
        )

    if "schema" not in keywords:
        violations.append(
            Violation(
                path,
                call.lineno,
                "postgresql.ENUM must declare schema=SCHEMA (schema-aware enums are required).",
            )
        )

    return violations


def check_sa_enum(path: Path, call: ast.Call) -> list[Violation]:
    keywords = keyword_map(call)
    if "name" in keywords:
        return [
            Violation(
                path,
                call.lineno,
                "sa.Enum(name=...) is запрещён in Alembic migrations.",
            )
        ]
    return []


def check_op_execute(path: Path, call: ast.Call) -> list[Violation]:
    if not call.args:
        return []
    sql = extract_string(call.args[0])
    if not sql:
        return []
    if "CREATE TYPE" in sql.upper():
        return [
            Violation(
                path,
                call.lineno,
                "Raw op.execute('CREATE TYPE ...') is запрещён; use ensure_pg_enum instead.",
            )
        ]
    return []


def gather_files(target_paths: list[Path]) -> tuple[list[Path], list[Path]]:
    if not target_paths:
        return list(iter_migration_files()), list(iter_model_files())

    migrations: list[Path] = []
    models: list[Path] = []

    for path in target_paths:
        try:
            resolved = path.resolve()
        except FileNotFoundError:
            continue
        if not resolved.exists() or resolved.suffix != ".py":
            continue

        try:
            relative = resolved.relative_to(PROJECT_ROOT)
        except ValueError:
            continue

        if "alembic/versions" in str(relative):
            migrations.append(resolved)
        elif MODEL_ROOT in resolved.parents:
            models.append(resolved)

    return migrations, models


def scan_file(path: Path, *, check_sa: bool) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Violation(path, 1, f"Unable to read file: {exc}")]

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return [Violation(path, line, f"Unable to parse file: {exc.msg}")]

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if is_postgresql_enum(node):
                violations.extend(check_postgresql_enum(path, node))
            if check_sa and is_sa_enum(node):
                violations.extend(check_sa_enum(path, node))
            if check_sa and is_op_execute(node):
                violations.extend(check_op_execute(path, node))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check enum policy in Alembic migrations and models.")
    parser.add_argument("paths", nargs="*", help="Optional list of files to scan.")
    args = parser.parse_args()

    target_paths = [Path(path) for path in args.paths]
    migration_files, model_files = gather_files(target_paths)

    violations: list[Violation] = []
    for path in sorted(set(migration_files)):
        violations.extend(scan_file(path, check_sa=True))
    for path in sorted(set(model_files)):
        violations.extend(scan_file(path, check_sa=False))

    if not violations:
        return 0

    for violation in violations:
        rel_path = violation.path.relative_to(PROJECT_ROOT)
        print(f"{rel_path}:{violation.line}: {violation.message}")
        print(f"  Fix: {FORBIDDEN_HINT}")

    return 1


if __name__ == "__main__":
    sys.exit(main())

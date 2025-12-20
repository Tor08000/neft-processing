from __future__ import annotations

import ast
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _iter_calls(target: str):
    assert VERSIONS_DIR.is_dir(), f"versions directory missing at {VERSIONS_DIR}"
    for path in VERSIONS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == target:
                yield path.name, node


def test_index_exists_contract():
    offenders: list[str] = []
    for filename, call in _iter_calls("index_exists"):
        if len(call.args) < 2:
            offenders.append(f"{filename}: not enough positional args")
            continue
        bad_kwargs = [
            kw.arg for kw in call.keywords if kw.arg not in (None, "schema")
        ]
        if bad_kwargs:
            offenders.append(f"{filename}: bad kwargs {bad_kwargs}")
            continue
        kw_names = {kw.arg for kw in call.keywords if kw.arg}
        disallowed = {"table_name", "inspector", "bind"} & kw_names
        if disallowed:
            offenders.append(f"{filename}: disallowed kwargs {sorted(disallowed)}")
    assert not offenders, (
        "index_exists contract violations:\n"
        + "\n".join(offenders)
        + "\nDo not pass table_name to index_exists; use op.create_index with table_name instead."
    )


def test_constraint_exists_contract():
    offenders: list[str] = []
    for filename, call in _iter_calls("constraint_exists"):
        if len(call.args) < 3:
            offenders.append(f"{filename}: expected bind, table_name, constraint_name")
            continue
        bad_kwargs = [
            kw.arg for kw in call.keywords if kw.arg not in (None, "schema")
        ]
        if bad_kwargs:
            offenders.append(f"{filename}: bad kwargs {bad_kwargs}")
            continue
        kw_names = {kw.arg for kw in call.keywords if kw.arg}
        disallowed = {"table_name", "inspector", "bind"} & kw_names
        if disallowed:
            offenders.append(f"{filename}: disallowed kwargs {sorted(disallowed)}")
    assert not offenders, "constraint_exists contract violations:\n" + "\n".join(offenders)

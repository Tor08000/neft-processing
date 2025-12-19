import ast
import re
from pathlib import Path

FORBIDDEN_PLACEHOLDER = re.compile(r":\w|%\([^)]+\)s")
APP_DIR = Path(__file__).resolve().parents[1]


def _has_placeholder(node: ast.AST) -> bool:
    if isinstance(node, (ast.Constant, ast.Str)) and isinstance(getattr(node, "value", None), str):
        return bool(FORBIDDEN_PLACEHOLDER.search(node.value))
    if isinstance(node, ast.JoinedStr):
        literal_parts = "".join([part.value for part in node.values if isinstance(part, ast.Constant)])
        return bool(FORBIDDEN_PLACEHOLDER.search(literal_parts))
    if isinstance(node, ast.Call):
        func = node.func
        func_name = getattr(func, "id", None) or getattr(func, "attr", None)
        if func_name == "text" and node.args:
            return _has_placeholder(node.args[0])
    return False


def _exec_driver_sql_violations(path: Path) -> list[str]:
    violations: list[str] = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "exec_driver_sql":
            continue

        has_params_arg = len(node.args) > 1 or any(kw.arg == "params" for kw in node.keywords)
        has_placeholder = bool(node.args) and _has_placeholder(node.args[0])
        if has_params_arg or has_placeholder:
            violations.append(f"{path}:{node.lineno}")
    return violations


def test_exec_driver_sql_has_no_parameters():
    paths = [p for p in APP_DIR.rglob("*.py") if "tests" not in p.parts]
    bad_calls: list[str] = []
    for path in paths:
        bad_calls.extend(_exec_driver_sql_violations(path))

    assert not bad_calls, f"exec_driver_sql must not use params or placeholders; found: {bad_calls}"

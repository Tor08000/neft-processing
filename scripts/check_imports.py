#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "platform" / "processing-core"
SOURCE_ROOT = PROJECT_ROOT / "app"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"

STDLIB = set(getattr(sys, "stdlib_module_names", set()))
LOCAL_MODULES = {
    p.name
    for p in PROJECT_ROOT.iterdir()
    if p.is_dir() and (p / "__init__.py").exists()
}
LOCAL_MODULES.update({"app", "neft_shared"})

IMPORT_TO_PACKAGE = {
    "dotenv": "python-dotenv",
    "email_validator": "email-validator",
    "jose": "python-jose",
    "multipart": "python-multipart",
    "prometheus_client": "prometheus-client",
    "psycopg": "psycopg",
    "yaml": "PyYAML",
    "PIL": "Pillow",
    "dateutil": "python-dateutil",
}


REQ_SPLIT_RE = re.compile(r"(==|>=|<=|~=|!=|<|>)")


def _normalize_requirement(raw: str) -> str:
    req = raw.strip().split("#", 1)[0].strip()
    if not req:
        return ""
    req = REQ_SPLIT_RE.split(req, maxsplit=1)[0]
    req = req.split("[", 1)[0]
    return req.strip().lower().replace("_", "-")


def load_requirements(path: Path) -> set[str]:
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        normalized = _normalize_requirement(line)
        if normalized:
            result.add(normalized)
    return result


def iter_python_files(root: Path):
    for file_path in root.rglob("*.py"):
        parts = set(file_path.parts)
        if "tests" in parts or "__pycache__" in parts or "alembic" in parts:
            continue
        yield file_path


def find_third_party_imports(root: Path) -> dict[str, list[str]]:
    imports: dict[str, list[str]] = {}
    for file_path in iter_python_files(root):
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".", 1)[0]
                    imports.setdefault(name, []).append(f"{file_path}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue
                name = node.module.split(".", 1)[0]
                imports.setdefault(name, []).append(f"{file_path}:{node.lineno}")
    for name in list(imports):
        if name in STDLIB or name in LOCAL_MODULES:
            imports.pop(name, None)
    return imports


def main() -> int:
    declared = load_requirements(REQUIREMENTS_FILE)
    imports = find_third_party_imports(SOURCE_ROOT)

    missing: dict[str, list[str]] = {}
    for module_name, locations in sorted(imports.items()):
        package_name = IMPORT_TO_PACKAGE.get(module_name, module_name).lower().replace("_", "-")
        if package_name not in declared:
            missing[module_name] = locations[:5]

    if missing:
        print("missing third-party imports:")
        for module_name, locations in missing.items():
            package_name = IMPORT_TO_PACKAGE.get(module_name, module_name)
            print(f"- module '{module_name}' -> package '{package_name}'")
            for location in locations:
                print(f"    {location}")
        return 1

    print("OK: all third-party imports are covered by requirements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

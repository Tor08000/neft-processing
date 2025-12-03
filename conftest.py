from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
SHARED_PATH = PROJECT_ROOT / "shared" / "python"
SERVICE_ROOTS = {
    "ai-service": PROJECT_ROOT / "services" / "ai-service",
    "auth-host": PROJECT_ROOT / "services" / "auth-host",
    "core-api": PROJECT_ROOT / "services" / "core-api",
    "workers": PROJECT_ROOT / "services" / "workers",
}


def _clean_modules(prefixes: Iterable[str]) -> None:
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(module_name)


def _prune_service_paths() -> None:
    service_paths = {str(path) for path in SERVICE_ROOTS.values() if path.exists()}
    sys.path[:] = [entry for entry in sys.path if entry not in service_paths]


def pytest_runtest_setup(item):  # type: ignore[override]
    _clean_modules(["app"])
    _prune_service_paths()

    if SHARED_PATH.exists():
        sys.path.insert(0, str(SHARED_PATH))

    node_path = Path(getattr(item, "fspath", getattr(item, "path", "")))
    for root in SERVICE_ROOTS.values():
        if root in node_path.parents and root.exists():
            sys.path.insert(0, str(root))
            break

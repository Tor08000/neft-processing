from __future__ import annotations

import sys
from pathlib import Path
import importlib
from typing import Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
SHARED_PATH = PROJECT_ROOT / "shared" / "python"
SERVICE_ROOTS = {
    "ai-service": PROJECT_ROOT / "platform" / "ai-services" / "risk-scorer",
    "auth-host": PROJECT_ROOT / "platform" / "auth-host",
    "core-api": PROJECT_ROOT / "platform" / "processing-core",
    "workers": PROJECT_ROOT / "platform" / "billing-clearing",
}


def _clean_modules(prefixes: Iterable[str], keep_root: Optional[Path] = None) -> None:
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes):
            module = sys.modules.get(module_name)
            module_file_attr = getattr(module, "__file__", None) if module else None
            module_file = Path(module_file_attr).resolve() if module_file_attr else None
            if keep_root and module_file and module_file.is_relative_to(keep_root):
                continue
            sys.modules.pop(module_name, None)


def _prune_service_paths() -> None:
    service_paths = {str(path) for path in SERVICE_ROOTS.values() if path.exists()}
    sys.path[:] = [entry for entry in sys.path if entry not in service_paths]


def _detect_service_root(node_path: Path) -> Optional[Path]:
    for root in SERVICE_ROOTS.values():
        if root in node_path.parents and root.exists():
            return root
    return None


def _prepare_paths(node_path: Path) -> Optional[Path]:
    current_root = _detect_service_root(node_path)

    _clean_modules(["app"], keep_root=current_root)
    _prune_service_paths()

    if SHARED_PATH.exists():
        sys.path.insert(0, str(SHARED_PATH))

    if current_root:
        sys.path.insert(0, str(current_root))
        importlib.invalidate_caches()

        keys_module = current_root / "app" / "services" / "keys.py"
        if keys_module.exists():
            importlib.import_module("app.services.keys")

    return current_root


def pytest_collect_file(file_path, parent):  # type: ignore[override]
    _prepare_paths(Path(file_path))
    return None


def pytest_runtest_setup(item):  # type: ignore[override]
    node_path = Path(getattr(item, "fspath", getattr(item, "path", "")))
    _prepare_paths(node_path)

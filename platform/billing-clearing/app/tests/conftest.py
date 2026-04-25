from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SHARED_PATH = PROJECT_ROOT / "shared" / "python"
SERVICE_ROOT = PROJECT_ROOT / "services" / "workers"
_SERVICE_DEPS_AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("celery", "sqlalchemy"))


def pytest_ignore_collect(collection_path, config):  # noqa: ANN001
    if collection_path.name == "conftest.py":
        return False
    return not _SERVICE_DEPS_AVAILABLE

for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

for path in (SHARED_PATH, SERVICE_ROOT):
    if path.exists():
        sys.path.insert(0, str(path))

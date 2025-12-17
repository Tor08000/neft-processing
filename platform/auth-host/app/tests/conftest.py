from __future__ import annotations

import os
import sys
from pathlib import Path


def _prioritize_service(service_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    sys.path.insert(0, str(service_root))


def _prepend_path(path: Path) -> None:
    if not path.exists():
        return

    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _find_repo_root(start: Path) -> Path:
    env_root = os.environ.get("REPO_ROOT") or os.environ.get("APP_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.exists():
            return candidate

    current = start
    fallback: Path | None = None

    for _ in range(15):
        if (current / ".git").exists() or (current / "docker-compose.yml").exists():
            return current

        if (current / "platform").exists() and (current / "shared").exists():
            fallback = current
        elif (current / "pyproject.toml").exists():
            fallback = fallback or current

        if current.parent == current:
            break
        current = current.parent

    return fallback or start


root = _find_repo_root(Path(__file__).resolve().parent)
shared_path = root / "shared" / "python"
service_root = root / "platform" / "auth-host"

_prepend_path(shared_path)

if service_root.exists():
    _prioritize_service(service_root)

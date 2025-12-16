import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _ensure_stdlib_platform_module() -> None:
    """Force the standard library ``platform`` module to be loaded.

    The repository has a top-level ``platform`` namespace package which can
    shadow Python's standard library module of the same name. Third-party
    dependencies such as SQLAlchemy rely on the stdlib implementation, so we
    temporarily remove repository paths from ``sys.path`` while importing
    ``platform`` and then register that module explicitly in ``sys.modules``.
    """

    removed_paths = []
    for entry in ("", str(ROOT)):
        if entry in sys.path:
            sys.path.remove(entry)
            removed_paths.append(entry)

    stdlib_platform = importlib.import_module("platform")
    sys.modules["platform"] = stdlib_platform

    for entry in reversed(removed_paths):
        sys.path.insert(0, entry)


_ensure_stdlib_platform_module()
paths = [
    ROOT / "services" / "auth-host",
    ROOT / "shared" / "python",
]
for path in paths:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from __future__ import annotations

import importlib.util
import sys
import sysconfig
from pathlib import Path


def _load_stdlib_platform_module() -> None:
    module = sys.modules.get("platform")
    if module is not None and hasattr(module, "python_implementation"):
        return

    stdlib_platform_path = Path(sysconfig.get_path("stdlib")) / "platform.py"
    spec = importlib.util.spec_from_file_location("platform", stdlib_platform_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("stdlib_platform_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules["platform"] = module
    spec.loader.exec_module(module)


def _prepend_service_root() -> None:
    service_root = Path(__file__).resolve().parents[2]
    service_root_str = str(service_root)
    if service_root_str not in sys.path:
        sys.path.insert(0, service_root_str)


_load_stdlib_platform_module()
_prepend_service_root()

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_app_path() -> None:
    service_root = Path(__file__).resolve().parents[2]
    service_root_str = str(service_root)
    if service_root_str not in sys.path:
        sys.path.insert(0, service_root_str)


_ensure_app_path()

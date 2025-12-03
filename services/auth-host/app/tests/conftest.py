from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
shared_path = root / "shared" / "python"
service_root = root / "services" / "auth-host"

for path in (shared_path, service_root):
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

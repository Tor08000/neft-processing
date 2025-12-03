from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SHARED_PATH = PROJECT_ROOT / "shared" / "python"
SERVICE_ROOT = PROJECT_ROOT / "services" / "workers"

for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

for path in (SHARED_PATH, SERVICE_ROOT):
    if path.exists():
        sys.path.insert(0, str(path))

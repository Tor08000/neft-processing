from __future__ import annotations

import sys
from pathlib import Path


def _prioritize_service(service_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    sys.path.insert(0, str(service_root))


root = Path(__file__).resolve().parents[5]
shared_path = root / "shared" / "python"
service_root = root / "platform" / "ai-services" / "risk-scorer"

for path in (shared_path,):
    if path.exists():
        sys.path.insert(0, str(path))

if service_root.exists():
    _prioritize_service(service_root)

from __future__ import annotations

import sys
from pathlib import Path


def _prioritize_service(service_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    sys.path.insert(0, str(service_root))


root = Path(__file__).resolve().parents[4]
shared_path = root / "shared" / "python"
service_root = root / "platform" / "auth-host"

for path in (shared_path,):
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

if service_root.exists():
    _prioritize_service(service_root)

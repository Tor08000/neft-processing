from __future__ import annotations

import sys
from pathlib import Path


def _prioritize_service(service_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    sys.path.insert(0, str(service_root))


test_file = Path(__file__).resolve()
repo_root = next(
    (
        parent
        for parent in test_file.parents
        if (parent / "platform" / "ai-services" / "risk-scorer").exists()
    ),
    None,
)

if repo_root is not None:
    shared_path = repo_root / "shared" / "python"
    service_root = repo_root / "platform" / "ai-services" / "risk-scorer"
else:
    shared_path = None
    service_root = next(
        (parent for parent in test_file.parents if (parent / "app" / "main.py").exists()),
        test_file.parents[2],
    )

for path in (shared_path,):
    if path is not None and path.exists():
        sys.path.insert(0, str(path))

if service_root.exists():
    _prioritize_service(service_root)

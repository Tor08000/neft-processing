import os
import sys
from pathlib import Path
import pytest


def pytest_configure():  # type: ignore[override]
    os.environ.setdefault("NEFT_AUTO_CREATE_SCHEMA", "false")
    repo_root = Path(__file__).resolve().parent
    shared_path = repo_root / "shared" / "python"
    shared_path_str = str(shared_path)
    if shared_path.exists() and shared_path_str not in sys.path:
        sys.path.insert(0, shared_path_str)


def _item_path(item) -> Path | None:
    path_str = str(getattr(item, "fspath", getattr(item, "path", "")))
    if not path_str:
        return None
    path = Path(path_str)
    try:
        return path.resolve()
    except OSError:
        return path


def pytest_collection_modifyitems(config, items):  # type: ignore[override]
    repo_root = Path(config.rootpath)
    host_tests_dir = (repo_root / "tests_host").resolve()
    known_marks = {
        "unit",
        "integration",
        "smoke",
        "contracts",
        "contracts_api",
        "contracts_events",
    }
    for item in items:
        item_path = _item_path(item)
        if not item_path:
            continue
        if host_tests_dir not in item_path.parents and item_path != host_tests_dir:
            continue
        path_str = str(item_path)
        if "/tests/smoke/" in path_str or "\\tests\\smoke\\" in path_str:
            item.add_marker("smoke")
        if "/tests/integration/" in path_str or "\\tests\\integration\\" in path_str:
            item.add_marker("integration")
        if "/tests/contracts/" in path_str or "\\tests\\contracts\\" in path_str:
            item.add_marker("contracts")
        if not any(item.get_closest_marker(mark) for mark in known_marks):
            item.add_marker("unit")

        if item.get_closest_marker("processing_core_required"):
            if os.environ.get("NEFT_PROCESSING_CORE_TESTS") != "1":
                item.add_marker(
                    pytest.mark.skip(
                        reason="processing-core tests disabled (set NEFT_PROCESSING_CORE_TESTS=1)"
                    )
                )

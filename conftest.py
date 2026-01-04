from pathlib import Path


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

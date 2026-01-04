def pytest_collection_modifyitems(config, items):  # type: ignore[override]
    known_marks = {
        "unit",
        "integration",
        "smoke",
        "contracts",
        "contracts_api",
        "contracts_events",
    }
    for item in items:
        path = str(getattr(item, "fspath", getattr(item, "path", "")))
        if "/tests/smoke/" in path:
            item.add_marker("smoke")
        if "/tests/integration/" in path:
            item.add_marker("integration")
        if "/tests/contracts/" in path:
            item.add_marker("contracts")
        if not any(item.get_closest_marker(mark) for mark in known_marks):
            item.add_marker("unit")

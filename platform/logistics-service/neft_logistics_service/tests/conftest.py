from __future__ import annotations

import os
import sys
import tempfile
import types
import importlib.util


_SERVICE_DEPS_AVAILABLE = importlib.util.find_spec("fastapi") is not None


def pytest_ignore_collect(collection_path, config):  # noqa: ANN001
    if collection_path.name == "conftest.py":
        return False
    return not _SERVICE_DEPS_AVAILABLE

os.environ.setdefault(
    "LOGISTICS_IDEMPOTENCY_DB_PATH",
    os.path.join(tempfile.gettempdir(), "neft-logistics-idempotency-test.sqlite3"),
)


try:
    import prometheus_client as _prometheus_client  # noqa: F401
except ModuleNotFoundError:
    _registered_metric_names: set[str] = set()

    class _TestMetric:
        def __init__(self, name: str, *_args, **_kwargs) -> None:
            self.name = name
            _registered_metric_names.add(name)

        def labels(self, *_args, **_kwargs):
            return self

        def inc(self, *_args, **_kwargs) -> None:
            return None

        def observe(self, *_args, **_kwargs) -> None:
            return None

    prometheus_stub = types.ModuleType("prometheus_client")
    prometheus_stub.CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    prometheus_stub.Counter = _TestMetric
    prometheus_stub.Histogram = _TestMetric
    prometheus_stub.generate_latest = lambda: "\n".join(sorted(_registered_metric_names)).encode("utf-8")
    sys.modules["prometheus_client"] = prometheus_stub

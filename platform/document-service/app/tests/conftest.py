from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


class _Metric:
    def labels(self, *args, **kwargs):
        return self

    def inc(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def observe(self, *args, **kwargs):
        return None


class _Registry:
    def __init__(self) -> None:
        self._names_to_collectors = {}
        self._collector_to_names = {}


if "prometheus_client" not in sys.modules:
    sys.modules["prometheus_client"] = types.SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=lambda *args, **kwargs: _Metric(),
        Gauge=lambda *args, **kwargs: _Metric(),
        Histogram=lambda *args, **kwargs: _Metric(),
        generate_latest=lambda: b"document_service_up 1\n",
        REGISTRY=_Registry(),
    )


class _Template:
    def __init__(self, template_html: str) -> None:
        self._template_html = template_html

    def render(self, **data):
        rendered = self._template_html
        for key, value in data.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered


class _Environment:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def from_string(self, template_html: str):
        return _Template(template_html)


if "jinja2" not in sys.modules:
    sys.modules["jinja2"] = types.SimpleNamespace(Environment=_Environment, StrictUndefined=object())


def _ensure_app_path() -> None:
    service_root = Path(__file__).resolve().parents[2]
    service_root_str = str(service_root)
    if service_root_str not in sys.path:
        sys.path.insert(0, service_root_str)


_ensure_app_path()


@pytest.fixture(autouse=True)
def _explicit_signing_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PROVIDER_X_MODE", "mock")
    monkeypatch.delenv("PROVIDER_X_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS_IN_PROD", raising=False)

    import app.sign.registry as sign_registry

    sign_registry._default_registry = None
    try:
        yield
    finally:
        sign_registry._default_registry = None

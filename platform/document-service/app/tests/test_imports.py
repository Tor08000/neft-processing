from __future__ import annotations

import importlib
import importlib.abc
import sys
from pathlib import Path

from prometheus_client import REGISTRY


class _BlockWeasyPrintFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if fullname == "weasyprint" or fullname.startswith("weasyprint."):
            raise ImportError("blocked weasyprint import")
        return None


def test_main_import_does_not_require_weasyprint(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "app.main", raising=False)
    monkeypatch.delitem(sys.modules, "app.renderer", raising=False)
    REGISTRY._names_to_collectors.clear()
    REGISTRY._collector_to_names.clear()

    finder = _BlockWeasyPrintFinder()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    importlib.import_module("app.main")


def test_dockerfile_declares_weasyprint_system_dependencies() -> None:
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    required_packages = {
        "fontconfig",
        "fonts-dejavu-core",
        "libgdk-pixbuf-2.0-0",
        "libglib2.0-0",
        "libpango-1.0-0",
        "libpangoft2-1.0-0",
        "shared-mime-info",
    }

    missing = sorted(package for package in required_packages if package not in content)
    assert missing == []


def test_weasyprint_renderer_dependency_versions_are_pinned() -> None:
    requirements = (Path(__file__).resolve().parents[2] / "requirements.txt").read_text(encoding="utf-8")

    assert "weasyprint==62.3" in requirements
    assert "pydyf==0.10.0" in requirements

from __future__ import annotations

import importlib
import importlib.abc
import sys


class _BlockWeasyPrintFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if fullname == "weasyprint" or fullname.startswith("weasyprint."):
            raise ImportError("blocked weasyprint import")
        return None


def test_main_import_does_not_require_weasyprint(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "app.main", raising=False)
    monkeypatch.delitem(sys.modules, "app.renderer", raising=False)

    finder = _BlockWeasyPrintFinder()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    importlib.import_module("app.main")

import importlib


def test_conftest_importable():
    importlib.import_module("app.tests.conftest")
    # Import should succeed without mutating sys.modules in a way that breaks pytest

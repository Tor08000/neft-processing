from app.main import app


def test_app_smoke_import_and_routes() -> None:
    assert app is not None

    paths = [route.path for route in app.router.routes if hasattr(route, "path")]
    assert paths
    assert any(path.startswith("/api/v1/admin") for path in paths)
    assert any(path.startswith("/client/api/v1") for path in paths)
    assert any(path.startswith("/api/v1/client/me") for path in paths)
    assert any(path.startswith("/api/v1/client/documents") for path in paths)

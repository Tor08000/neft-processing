from fastapi import APIRouter, FastAPI

from app.fastapi_utils import safe_include_router


def _router() -> APIRouter:
    router = APIRouter()

    @router.get('/dup')
    def _endpoint() -> dict[str, str]:
        return {'ok': '1'}

    return router


def test_router_duplicates_error_mode(monkeypatch) -> None:
    app = FastAPI()
    safe_include_router(app, _router())
    monkeypatch.setenv('ROUTER_DUPLICATES_MODE', 'error')

    try:
        safe_include_router(app, _router())
        raise AssertionError('expected RuntimeError')
    except RuntimeError as exc:
        assert 'Duplicate routes detected' in str(exc)


def test_router_duplicates_ignore_mode(monkeypatch) -> None:
    app = FastAPI()
    safe_include_router(app, _router())
    monkeypatch.setenv('ROUTER_DUPLICATES_MODE', 'ignore')

    safe_include_router(app, _router())
    dup_routes = [r for r in app.routes if getattr(r, 'path', None) == '/dup']
    assert len(dup_routes) == 1

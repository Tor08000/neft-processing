from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def _find_route(path: str, method: str) -> APIRoute | None:
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in (route.methods or set()):
            return route
    return None


def test_admin_users_public_and_auth_prefixed_routes_stay_mounted() -> None:
    public_paths = {
        ("GET", "/api/v1/admin/users"),
        ("POST", "/api/v1/admin/users"),
        ("PATCH", "/api/v1/admin/users/{user_id}"),
        ("GET", "/api/auth/v1/admin/users"),
        ("POST", "/api/auth/v1/admin/users"),
        ("PATCH", "/api/auth/v1/admin/users/{user_id}"),
    }

    for method, path in public_paths:
        route = _find_route(path, method)
        assert route is not None, f"route missing: {method} {path}"
        assert route.include_in_schema is True

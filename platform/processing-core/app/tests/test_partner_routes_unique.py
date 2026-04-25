from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def _route_count(method: str, path: str) -> int:
    count = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = route.methods or set()
        if method in methods and route.path == path:
            count += 1
    return count


def test_partner_routes_registered_once() -> None:
    expected_routes = [
        ("GET", "/api/partner/profile"),
        ("PATCH", "/api/partner/profile"),
        ("GET", "/api/partner/orders"),
        ("GET", "/api/partner/orders/{order_id}"),
        ("POST", "/api/partner/orders/{order_id}/accept"),
        ("POST", "/api/partner/orders/{order_id}/reject"),
    ]

    for method, path in expected_routes:
        assert _route_count(method, path) == 1

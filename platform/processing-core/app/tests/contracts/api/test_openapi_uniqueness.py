from __future__ import annotations

from collections import defaultdict

import pytest
from fastapi.routing import APIRoute

from app.main import app

pytestmark = [pytest.mark.contracts, pytest.mark.contracts_api]


def _route_key(route: APIRoute, method: str) -> tuple[str, str]:
    return method, route.path


def _endpoint_key(route: APIRoute) -> tuple[str, str, str]:
    return route.endpoint.__module__, route.endpoint.__name__, route.path


def _iter_routes():
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route


def test_routes_unique_method_path() -> None:
    ignored_methods = {"HEAD", "OPTIONS"}
    method_path_map: dict[tuple[str, str], list[APIRoute]] = defaultdict(list)
    endpoint_path_map: dict[tuple[str, str, str], list[APIRoute]] = defaultdict(list)

    for route in _iter_routes():
        methods = {method for method in (route.methods or set()) if method not in ignored_methods}
        for method in methods:
            method_path_map[_route_key(route, method)].append(route)
        endpoint_path_map[_endpoint_key(route)].append(route)

    duplicates = {key: routes for key, routes in method_path_map.items() if len(routes) > 1}
    endpoint_duplicates = {key: routes for key, routes in endpoint_path_map.items() if len(routes) > 1}

    if duplicates:
        lines = ["Duplicate method/path routes detected:"]
        for (method, path), routes in sorted(duplicates.items()):
            endpoints = ", ".join(
                sorted({f"{route.endpoint.__module__}.{route.endpoint.__name__}" for route in routes})
            )
            lines.append(f"{method} {path} -> {endpoints}")
        raise AssertionError("\n".join(lines))

    if endpoint_duplicates:
        lines = ["Duplicate endpoint/module/path routes detected:"]
        for (module, name, path), routes in sorted(endpoint_duplicates.items()):
            lines.append(f"{module}.{name} {path} ({len(routes)})")
        raise AssertionError("\n".join(lines))


def test_openapi_operation_ids_unique() -> None:
    schema = app.openapi()
    operation_map: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            operation_map[operation_id].append((method.upper(), path))

    duplicates = {op_id: entries for op_id, entries in operation_map.items() if len(entries) > 1}

    if duplicates:
        lines = ["Duplicate operationId entries detected:"]
        for op_id, entries in sorted(duplicates.items()):
            paths = ", ".join(sorted({f"{method} {path}" for method, path in entries}))
            lines.append(f"{op_id} -> {paths}")
        raise AssertionError("\n".join(lines))

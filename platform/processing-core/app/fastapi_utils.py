from __future__ import annotations

import os
from collections import defaultdict
from typing import Iterable

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


def generate_unique_id(route: APIRoute) -> str:
    methods = "-".join(sorted(route.methods or []))
    module = route.endpoint.__module__
    return f"{module}.{route.name}:{methods}:{route.path_format}"

def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    normalized = prefix if prefix.startswith("/") else f"/{prefix}"
    return normalized.rstrip("/")


def _combine_prefix(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if path == "/":
        return prefix or "/"
    return f"{prefix}{path}"


def _iter_routes(router: APIRouter | FastAPI) -> Iterable[APIRoute]:
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route


_IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _collect_route_keys(
    router: APIRouter | FastAPI,
    prefix: str = "",
) -> dict[tuple[str, str], list[APIRoute]]:
    normalized_prefix = _normalize_prefix(prefix)
    keys: dict[tuple[str, str], list[APIRoute]] = defaultdict(list)
    for route in _iter_routes(router):
        methods = {method for method in (route.methods or set()) if method not in _IGNORED_METHODS}
        full_path = _combine_prefix(normalized_prefix, route.path)
        for method in methods:
            keys[(method, full_path)].append(route)
    return keys


def _router_source(router: APIRouter, source: str | None) -> str:
    if source:
        return source
    module = getattr(router, "__module__", None)
    if module:
        return module
    return router.__class__.__module__


def _route_source_map(
    target: APIRouter | FastAPI,
) -> dict[tuple[str, str], str]:
    sources: dict[tuple[str, str], str] | None = getattr(target, "_route_sources", None)
    if sources is not None:
        return sources
    sources = {}
    for route in _iter_routes(target):
        methods = {method for method in (route.methods or set()) if method not in _IGNORED_METHODS}
        for method in methods:
            sources[(method, route.path)] = route.endpoint.__module__
    setattr(target, "_route_sources", sources)
    return sources


def safe_include_router(
    target: APIRouter | FastAPI,
    router: APIRouter,
    *,
    prefix: str = "",
    source: str | None = None,
    **kwargs: object,
) -> None:
    existing_keys = _collect_route_keys(target)
    incoming_keys = _collect_route_keys(router, prefix=prefix)
    existing_sources = _route_source_map(target)
    incoming_source = _router_source(router, source)
    overlapping: dict[tuple[str, str], list[APIRoute]] = {}
    for key, routes in incoming_keys.items():
        if key in existing_keys:
            overlapping[key] = routes

    if overlapping:
        lines = ["Duplicate routes detected while including router:"]
        for (method, path), routes in sorted(overlapping.items()):
            names = ", ".join(sorted({route.name for route in routes}))
            existing_source = existing_sources.get(
                (method, path),
                existing_keys[(method, path)][0].endpoint.__module__,
            )
            lines.append(
                f"{method} {path} -> {names} "
                f"(first: {existing_source}, second: {incoming_source})"
            )
        message = "\n".join(lines)
        if os.getenv("NEFT_STRICT_ROUTES", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError(message)
        logger.warning(message)
        return

    target.include_router(router, prefix=_normalize_prefix(prefix), **kwargs)
    route_sources = _route_source_map(target)
    for key in incoming_keys:
        route_sources[key] = incoming_source


__all__ = ["generate_unique_id", "safe_include_router"]

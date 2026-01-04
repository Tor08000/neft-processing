from __future__ import annotations

from fastapi.routing import APIRoute


def generate_unique_id(route: APIRoute) -> str:
    methods = "-".join(sorted(route.methods or []))
    module = route.endpoint.__module__
    return f"{module}.{route.name}:{methods}:{route.path_format}"


__all__ = ["generate_unique_id"]

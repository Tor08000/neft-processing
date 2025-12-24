#!/usr/bin/env python3
"""Find FastAPI auth-host endpoints by scanning router decorators.

Usage:
  python find_auth_endpoints.py --root platform/auth-host/app
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass


ROUTE_PATTERN = re.compile(
    r"@router\.(?P<method>get|post|put|patch|delete|options|head)"
    r"\(\s*(?P<quote>['\"])(?P<path>.*?)(?P=quote)"
)


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    location: str


def iter_python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return [path for path in root.rglob("*.py") if path.is_file()]


def find_endpoints(root: pathlib.Path) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for path in iter_python_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[WARN] Failed to read {path}: {exc}", file=sys.stderr)
            continue

        for match in ROUTE_PATTERN.finditer(content):
            method = match.group("method").upper()
            route_path = match.group("path")
            line_no = content.count("\n", 0, match.start()) + 1
            endpoints.append(
                Endpoint(method=method, path=route_path, location=f"{path}:{line_no}")
            )
    return endpoints


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List auth-host FastAPI routes and their locations."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path("platform/auth-host/app"),
        help="Path to auth-host app package.",
    )
    args = parser.parse_args()

    root = args.root
    if not root.exists():
        print(f"[ERROR] Root path not found: {root}", file=sys.stderr)
        return 1

    endpoints = sorted(find_endpoints(root), key=lambda item: (item.path, item.method))
    if not endpoints:
        print("[WARN] No endpoints found. Check router decorators and path.")
        return 2

    print("METHOD\tPATH\tLOCATION")
    for endpoint in endpoints:
        print(f"{endpoint.method}\t{endpoint.path}\t{endpoint.location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi.routing import APIRoute

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "docs" / "diag" / "openapi"
REPORT_PATH = OUTPUT_DIR / "OPENAPI_REPORT.md"
SHARED_PYTHON = REPO_ROOT / "shared" / "python"


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    root: Path
    module: str
    app_attr: str = "app"


SERVICES: list[ServiceConfig] = [
    ServiceConfig("processing-core", REPO_ROOT / "platform" / "processing-core", "app.main"),
    ServiceConfig("auth-host", REPO_ROOT / "platform" / "auth-host", "app.main"),
    ServiceConfig("crm-service", REPO_ROOT / "platform" / "crm-service", "app.main"),
    ServiceConfig("document-service", REPO_ROOT / "platform" / "document-service", "app.main"),
    ServiceConfig("integration-hub", REPO_ROOT / "platform" / "integration-hub", "neft_integration_hub.main"),
    ServiceConfig("logistics-service", REPO_ROOT / "platform" / "logistics-service", "neft_logistics_service.main"),
]


def iter_http_rows(app) -> Iterable[tuple[str, str, str, str]]:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = sorted(m for m in (route.methods or set()) if m)
        endpoint = route.endpoint
        handler = f"{getattr(endpoint, '__module__', 'unknown')}:{getattr(endpoint, '__name__', 'unknown')}"
        operation_id = route.operation_id or ""
        for method in methods:
            yield method, route.path, operation_id, handler


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_env() -> None:
    defaults = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "DB_URL": "sqlite+pysqlite:///:memory:",
        "ASYNC_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/0",
        "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "SECRET_KEY": "dev-secret-key",
        "JWT_SECRET": "dev-secret-key",
        "ENV": "test",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def load_app(config: ServiceConfig):
    prepare_env()
    package_root = config.module.split(".", 1)[0]
    stale_modules = [name for name in sys.modules if name == package_root or name.startswith(f"{package_root}.")]
    for name in stale_modules:
        sys.modules.pop(name, None)

    extra_paths = [str(config.root), str(SHARED_PYTHON)]
    for extra in reversed(extra_paths):
        if extra in sys.path:
            sys.path.remove(extra)
        sys.path.insert(0, extra)

    module = importlib.import_module(config.module)
    return getattr(module, config.app_attr)


def dump_service(config: ServiceConfig) -> dict:
    app = load_app(config)
    rows = sorted(iter_http_rows(app), key=lambda row: (row[0], row[1], row[2], row[3]))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tsv_path = OUTPUT_DIR / f"{config.name}.routes.tsv"
    with tsv_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write("\t".join(row) + "\n")

    method_path_counts = Counter((method, path) for method, path, _, _ in rows)
    duplicate_method_path = sum(1 for count in method_path_counts.values() if count > 1)
    excess_rows = sum(count - 1 for count in method_path_counts.values() if count > 1)

    handlers_by_pair: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for method, path, _, handler in rows:
        handlers_by_pair[(method, path)].add(handler)

    duplicate_details: list[tuple[str, str, int, list[str]]] = []
    for (method, path), count in method_path_counts.items():
        if count > 1:
            duplicate_details.append((method, path, count, sorted(handlers_by_pair[(method, path)])))
    duplicate_details.sort(key=lambda item: (-item[2], item[0], item[1]))

    duplicates_tsv_path = OUTPUT_DIR / f"{config.name}.duplicates.tsv"
    with duplicates_tsv_path.open("w", encoding="utf-8") as fh:
        for method, path, count, handlers in duplicate_details:
            fh.write(f"{method}\t{path}\t{count}\t{','.join(handlers)}\n")

    operation_index: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
    for method, path, operation_id, _ in rows:
        if operation_id:
            operation_index[operation_id].add((method, path))

    collisions = {
        operation_id: sorted(entries)
        for operation_id, entries in operation_index.items()
        if len(entries) > 1
    }

    return {
        "name": config.name,
        "rows": rows,
        "total_routes": len(rows),
        "unique_method_path": len(method_path_counts),
        "duplicate_method_path": duplicate_method_path,
        "duplicate_excess_rows": excess_rows,
        "duplicate_details": duplicate_details,
        "duplicates_tsv_path": duplicates_tsv_path,
        "operation_collisions": collisions,
        "tsv_path": tsv_path,
        "sha256": sha256_file(tsv_path),
    }


def write_report(results: list[dict]) -> None:
    lines: list[str] = [
        "# OpenAPI Compact Route Report",
        "",
        "Generated by `scripts/diag/dump_openapi.py`.",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"## Service: {result['name']}",
                "",
                "### A. Сводка",
                f"Service: {result['name']}",
                f"Total routes: {result['total_routes']}",
                f"Unique method+path: {result['unique_method_path']}",
                f"Duplicate method+path: {result['duplicate_method_path']}",
                f"operationId collisions: {len(result['operation_collisions'])}",
                "",
                "### B. Top collisions (до 50)",
            ]
        )

        if result["operation_collisions"]:
            for operation_id in sorted(result["operation_collisions"].keys())[:50]:
                lines.append(f"Collision: operationId={operation_id}")
                for method, path in result["operation_collisions"][operation_id]:
                    lines.append(f"- {method} {path}")
        else:
            lines.append("No operationId collisions.")

        lines.extend(
            [
                "",
                "### C. Hash доказательство",
                f"SHA256({result['name']}.routes.tsv) = {result['sha256']}",
                "",
                "### D. Duplicate method+path details (top 50)",
                f"duplicated pairs: {result['duplicate_method_path']}",
                f"excess rows: {result['duplicate_excess_rows']}",
            ]
        )

        if result["duplicate_details"]:
            for method, path, count, handlers in result["duplicate_details"][:50]:
                lines.append(f"Duplicate: {method} {path} (count={count})")
                for handler in handlers:
                    lines.append(f"- {handler}")
        else:
            lines.append("No duplicate method+path rows.")

        lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump compact FastAPI route indexes for services")
    parser.add_argument("--service", action="append", help="Service name to dump; may be passed multiple times")
    args = parser.parse_args()

    selected = SERVICES
    if args.service:
        wanted = set(args.service)
        selected = [svc for svc in SERVICES if svc.name in wanted]
        missing = wanted - {svc.name for svc in selected}
        if missing:
            raise SystemExit(f"Unknown service(s): {', '.join(sorted(missing))}")

    results = [dump_service(service) for service in selected]
    write_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

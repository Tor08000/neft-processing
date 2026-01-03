from __future__ import annotations

import re

import psycopg

from tests.smoke.utils import (
    build_pg_dsn,
    http_get,
    qualified_regclass,
    read_json,
    schema_connect_kwargs,
    target_schema,
)


def _extract_asset_href(html: str, base_prefix: str) -> str:
    match = re.search(f'{re.escape(base_prefix)}assets/[^"\\\']+', html)
    if not match:
        raise AssertionError(f"No asset reference with prefix {base_prefix}assets/ found in html")
    return match.group(0)


def test_gateway_health_bootstrap():
    response = http_get("/health")
    body = response.read().decode()
    assert response.status == 200
    assert "OK" in body


def test_core_health_bootstrap():
    response = http_get("/api/core/health", expect_json=True)
    data = read_json(response)
    assert response.status == 200
    assert data.get("status") == "ok"


def test_admin_ui_bootstrap():
    response = http_get("/admin/")
    html = response.read().decode()
    assert response.status == 200
    assert "<html" in html.lower()

    asset_href = _extract_asset_href(html, "/admin/")
    asset_resp = http_get(asset_href)
    assert asset_resp.status == 200


def test_alembic_and_operations_regclass():
    dsn = build_pg_dsn()
    schema = target_schema()
    with psycopg.connect(dsn, **schema_connect_kwargs(schema)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (qualified_regclass("alembic_version", schema),))
            alembic_regclass = cur.fetchone()[0]

            cur.execute("SELECT to_regclass(%s)", (qualified_regclass("operations", schema),))
            operations_regclass = cur.fetchone()[0]

    assert alembic_regclass is not None, "alembic_version table is missing"
    assert operations_regclass is not None, "operations table is missing"

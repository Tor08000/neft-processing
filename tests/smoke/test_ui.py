from __future__ import annotations

import re

from tests.smoke.utils import build_url, http_get


def _extract_asset_href(html: str, base_prefix: str) -> str:
    match = re.search(rf"{re.escape(base_prefix)}assets/[^\\"']+", html)
    if not match:
        raise AssertionError(f"No asset reference with prefix {base_prefix}assets/ found in html")
    return match.group(0)


def test_admin_ui_served():
    response = http_get("/admin/")
    html = response.read().decode()
    assert response.status == 200
    assert "<html" in html.lower()

    asset_url = _extract_asset_href(html, "/admin/")
    asset_resp = http_get(asset_url)
    assert asset_resp.status == 200


def test_client_ui_served():
    response = http_get("/client/")
    html = response.read().decode()
    assert response.status == 200
    assert "<html" in html.lower()

    asset_url = _extract_asset_href(html, "/client/")
    asset_resp = http_get(asset_url)
    assert asset_resp.status == 200

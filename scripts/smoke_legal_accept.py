from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib import error, request


def _request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code} {body[:2048]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base core-api URL, e.g. http://localhost/api/core")
    parser.add_argument("--token", required=True, help="Bearer token")
    args = parser.parse_args()

    base = args.base.rstrip("/")

    status, payload = _request("GET", f"{base}/legal/required", args.token)
    if status != 200:
        raise RuntimeError(f"GET {base}/legal/required -> HTTP {status}")
    payload = payload or {}
    required = payload.get("required") or []

    missing_items = [item for item in required if not item.get("accepted")]
    for item in missing_items:
        accept_payload = {
            "code": item["code"],
            "version": item["required_version"],
            "locale": item["locale"],
            "accepted": True,
        }
        status, _ = _request("POST", f"{base}/legal/accept", args.token, accept_payload)
        if status != 204:
            raise RuntimeError(f"POST {base}/legal/accept -> HTTP {status}")

    if missing_items:
        status, payload = _request("GET", f"{base}/legal/required", args.token)
        if status != 200:
            raise RuntimeError(f"GET {base}/legal/required -> HTTP {status}")
        payload = payload or {}
        remaining = [item for item in (payload.get("required") or []) if not item.get("accepted")]
        if remaining:
            raise RuntimeError("Legal documents still required after acceptance.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)

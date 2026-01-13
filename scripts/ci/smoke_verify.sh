#!/usr/bin/env bash
set -euo pipefail

export AUTH_URL="${AUTH_URL:-http://auth-host:8000/api/v1/auth}"
export CORE_URL="${CORE_URL:-http://core-api:8000/api/core/v1/admin}"
export NEFT_BOOTSTRAP_ADMIN_EMAIL="${NEFT_BOOTSTRAP_ADMIN_EMAIL:-admin@example.com}"
export NEFT_BOOTSTRAP_ADMIN_PASSWORD="${NEFT_BOOTSTRAP_ADMIN_PASSWORD:-admin}"

python - <<'PY'
import json
import os
import sys
import urllib.request

auth_url = os.getenv("AUTH_URL")
core_url = os.getenv("CORE_URL")
core_public = core_url.replace("/api/core/v1/admin", "/api/core")
email = os.getenv("NEFT_BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
password = os.getenv("NEFT_BOOTSTRAP_ADMIN_PASSWORD", "admin")


def fetch(url, *, method="GET", data=None, headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if data is not None:
        body = json.dumps(data).encode()
        req.data = body
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read()


status, body = fetch(f"{auth_url}/login", method="POST", data={"email": email, "password": password})
token = json.loads(body.decode()).get("access_token")
if not token:
    sys.exit("token missing")
headers = {"Authorization": f"Bearer {token}"}

payload = {
    "kind": "operation",
    "entity_id": "verify-smoke",
    "priority": "MEDIUM",
    "note": "smoke check",
}
status, body = fetch(f"{core_public}/cases", method="POST", data=payload, headers=headers)
case_id = json.loads(body.decode()).get("id")
if not case_id:
    sys.exit("case id missing")

status, body = fetch(f"{core_url}/cases/{case_id}/events/verify", method="POST", headers=headers)
verify = json.loads(body.decode())
if verify.get("signatures", {}).get("status") != "verified":
    sys.exit("event signatures not verified")

export_payload = {
    "kind": "CASE",
    "case_id": case_id,
    "payload": {"email": "smoke@example.com", "token": "secret"},
    "mastery_snapshot": None,
}
status, body = fetch(f"{core_url}/exports", method="POST", data=export_payload, headers=headers)
export_id = json.loads(body.decode()).get("id")
if not export_id:
    sys.exit("export id missing")

status, body = fetch(f"{core_url}/exports/{export_id}/verify", method="POST", headers=headers)
export_verify = json.loads(body.decode())
if not export_verify.get("artifact_signature_verified"):
    sys.exit("export signature not verified")

print("smoke verify ok")
PY

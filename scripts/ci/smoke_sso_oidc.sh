#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
TENANT_ID="${TENANT_ID:-00000000-0000-0000-0000-000000000000}"
PROVIDER_KEY="${PROVIDER_KEY:-corp-oidc}"
REDIRECT_URI="${REDIRECT_URI:-http://localhost:5173/login}"

echo "[smoke] list idps"
curl -fsS "${BASE_URL}/api/v1/auth/sso/idps?tenant_id=${TENANT_ID}&portal=client" >/dev/null

echo "[smoke] oidc start"
status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/auth/sso/oidc/start?tenant_id=${TENANT_ID}&provider_key=${PROVIDER_KEY}&portal=client&redirect_uri=${REDIRECT_URI}")
if [[ "${status}" != "302" ]]; then
  echo "expected 302 from oidc/start, got ${status}" >&2
  exit 1
fi

echo "[smoke] done"

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CORE_API_BASE_URL:-http://localhost:8080}"
TOKEN="${CLIENT_SMOKE_TOKEN:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "[smoke_client_users] CLIENT_SMOKE_TOKEN is not set; skipping smoke run"
  exit 0
fi

users_status=$(curl -sS -o /tmp/client_users_before.json -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  "${BASE_URL}/api/core/client/users")
[[ "${users_status}" == "200" ]]

invite_status=$(curl -sS -o /tmp/client_users_invite.json -w "%{http_code}" \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"email":"smoke.client.users@example.com","roles":["CLIENT_MANAGER"]}' \
  "${BASE_URL}/api/core/client/users/invite")
if [[ "${invite_status}" != "201" && "${invite_status}" != "409" ]]; then
  echo "[smoke_client_users] invite request failed with status ${invite_status}"
  cat /tmp/client_users_invite.json
  exit 1
fi

users_after_status=$(curl -sS -o /tmp/client_users_after.json -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  "${BASE_URL}/api/core/client/users")
[[ "${users_after_status}" == "200" ]]

echo "client users smoke passed"

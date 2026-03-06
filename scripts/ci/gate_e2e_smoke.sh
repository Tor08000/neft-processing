#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

extract_token() {
  python -c 'import json,sys; data=json.load(sys.stdin); print(data.get("access_token", ""))'
}

login() {
  local login="$1"
  local password="$2"
  local portal="$3"

  local payload
  payload=$(printf '{"login":"%s","password":"%s","portal":"%s"}' "$login" "$password" "$portal")

  local token
  token=$(curl -fsS -X POST "${BASE_URL}/api/v1/auth/login" -H 'content-type: application/json' -d "$payload" | extract_token)
  if [[ -z "$token" ]]; then
    echo "Unable to get token for portal=${portal}"
    return 1
  fi
  echo "$token"
}

assert_ok() {
  local token="$1"
  local endpoint="$2"
  curl -fsS "${BASE_URL}${endpoint}" -H "Authorization: Bearer ${token}" >/dev/null
}

admin_token=$(login "${ADMIN_LOGIN:-admin@example.com}" "${ADMIN_PASSWORD:-change-me}" "admin")
assert_ok "$admin_token" "/api/core/admin/me"

client_token=$(login "${CLIENT_LOGIN:-client@neft.local}" "${CLIENT_PASSWORD:-client}" "client")
assert_ok "$client_token" "/api/core/client/v1/me"

partner_token=$(login "${PARTNER_LOGIN:-partner@neft.local}" "${PARTNER_PASSWORD:-Partner123!}" "partner")
assert_ok "$partner_token" "/api/core/partner/me"

wrong_portal_code=$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}/api/core/admin/me" -H "Authorization: Bearer ${client_token}")
if [[ "$wrong_portal_code" != "403" ]]; then
  echo "Expected 403 for wrong portal token, got ${wrong_portal_code}"
  exit 1
fi

echo "Gateway e2e smoke passed"

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
LOGIN="${PARTNER_LOGIN:-partner@neft.local}"
PASSWORD="${PARTNER_PASSWORD:-partner}"

LOGIN_PAYLOAD=$(jq -n --arg login "$LOGIN" --arg password "$PASSWORD" '{login:$login,password:$password,portal:"partner"}')
TOKEN=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" -H "Content-Type: application/json" -d "$LOGIN_PAYLOAD" | jq -r '.access_token')

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "Failed to acquire partner token"
  exit 1
fi

curl -sS -f "$BASE_URL/api/core/partner/me" -H "Authorization: Bearer $TOKEN" >/dev/null

CREATE_LOCATION_BODY='{"title":"Smoke Location","address":"Smoke Address"}'
LOCATION_ID=$(curl -sS -f -X POST "$BASE_URL/api/core/partner/locations" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$CREATE_LOCATION_BODY" | jq -r '.id')

if [[ -z "$LOCATION_ID" || "$LOCATION_ID" == "null" ]]; then
  echo "Location was not created"
  exit 1
fi

curl -sS -f "$BASE_URL/api/core/partner/locations" -H "Authorization: Bearer $TOKEN" | jq -e --arg id "$LOCATION_ID" '.[] | select(.id == $id)' >/dev/null
curl -sS -f "$BASE_URL/api/core/partner/terms" -H "Authorization: Bearer $TOKEN" >/dev/null

echo "Partner smoke passed"

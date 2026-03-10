#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
CLIENT_EMAIL="${CLIENT_EMAIL:-demo.client@neft.app}"
CLIENT_PASSWORD="${CLIENT_PASSWORD:-demo12345}"
PARTNER_EMAIL="${PARTNER_EMAIL:-demo.partner@neft.app}"
PARTNER_PASSWORD="${PARTNER_PASSWORD:-demo12345}"
NEW_SIGNUP_EMAIL="${NEW_SIGNUP_EMAIL:-baseline.$(date +%s)@example.test}"
EXISTING_SIGNUP_EMAIL="${EXISTING_SIGNUP_EMAIL:-$CLIENT_EMAIL}"
SIGNUP_PASSWORD="${SIGNUP_PASSWORD:-Passw0rd!123}"

post_json() {
  local path="$1"
  local payload="$2"
  curl -sS -o /tmp/neft_smoke_resp.json -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$BASE_URL$path" \
    -d "$payload"
}

echo "[1/5] client login"
status=$(post_json "/api/auth/login" "{\"email\":\"$CLIENT_EMAIL\",\"password\":\"$CLIENT_PASSWORD\"}")
echo "status=$status"


echo "[2/5] signup with new email"
status=$(post_json "/api/auth/signup" "{\"email\":\"$NEW_SIGNUP_EMAIL\",\"password\":\"$SIGNUP_PASSWORD\"}")
echo "status=$status (expect success)"


echo "[3/5] signup with existing email"
status=$(post_json "/api/auth/signup" "{\"email\":\"$EXISTING_SIGNUP_EMAIL\",\"password\":\"$SIGNUP_PASSWORD\"}")
echo "status=$status (expect conflict/validation)"


echo "[4/5] demo showcase login"
status=$(post_json "/api/auth/login" "{\"email\":\"$CLIENT_EMAIL\",\"password\":\"$CLIENT_PASSWORD\"}")
echo "status=$status"


echo "[5/5] partner login"
status=$(post_json "/api/auth/login" "{\"email\":\"$PARTNER_EMAIL\",\"password\":\"$PARTNER_PASSWORD\"}")
echo "status=$status"

echo "Done. Validate UI flows manually using docs/baseline-smoke-checklist.md"

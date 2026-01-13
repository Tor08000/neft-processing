#!/usr/bin/env bash
set -euo pipefail

AUTH_BASE_URL="${AUTH_BASE_URL:-http://localhost:8000}"

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "missing required env: ${name}" >&2
    exit 1
  fi
}

require_env NEFT_BOOTSTRAP_ADMIN_EMAIL
require_env NEFT_BOOTSTRAP_ADMIN_PASSWORD
require_env NEFT_BOOTSTRAP_CLIENT_EMAIL
require_env NEFT_BOOTSTRAP_CLIENT_PASSWORD
require_env NEFT_BOOTSTRAP_PARTNER_EMAIL
require_env NEFT_BOOTSTRAP_PARTNER_PASSWORD

echo ">>> auth health"
curl -sS "${AUTH_BASE_URL}/api/auth/health"
echo ""

login() {
  local label="$1"
  local email="$2"
  local password="$3"
  local payload

  payload=$(printf '{"email":"%s","password":"%s"}' "$email" "$password")
  echo ">>> login ${label}"
  curl -sS -X POST "${AUTH_BASE_URL}/api/auth/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "${payload}"
  echo ""
}

login "admin" "${NEFT_BOOTSTRAP_ADMIN_EMAIL}" "${NEFT_BOOTSTRAP_ADMIN_PASSWORD}"
login "client" "${NEFT_BOOTSTRAP_CLIENT_EMAIL}" "${NEFT_BOOTSTRAP_CLIENT_PASSWORD}"
login "partner" "${NEFT_BOOTSTRAP_PARTNER_EMAIL}" "${NEFT_BOOTSTRAP_PARTNER_PASSWORD}"

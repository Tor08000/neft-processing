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
curl -sS -o /tmp/auth_health.json -w "%{http_code}" "${AUTH_BASE_URL}/api/auth/health" | {
  read -r status
  if [ "${status}" != "200" ]; then
    echo "auth health failed (status=${status})" >&2
    cat /tmp/auth_health.json >&2 || true
    exit 1
  fi
}
echo ""

login() {
  local label="$1"
  local email="$2"
  local password="$3"
  local payload

  payload=$(printf '{"email":"%s","password":"%s"}' "$email" "$password")
  echo ">>> login ${label}"
  curl -sS -o /tmp/auth_login.json -w "%{http_code}" -X POST "${AUTH_BASE_URL}/api/auth/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "${payload}" | {
      read -r status
      if [ "${status}" != "200" ]; then
        echo "login ${label} failed (status=${status})" >&2
        cat /tmp/auth_login.json >&2 || true
        exit 1
      fi
    }
  echo ""
}

login "admin" "${NEFT_BOOTSTRAP_ADMIN_EMAIL}" "${NEFT_BOOTSTRAP_ADMIN_PASSWORD}"
login "client" "${NEFT_BOOTSTRAP_CLIENT_EMAIL}" "${NEFT_BOOTSTRAP_CLIENT_PASSWORD}"
login "partner" "${NEFT_BOOTSTRAP_PARTNER_EMAIL}" "${NEFT_BOOTSTRAP_PARTNER_PASSWORD}"

echo ">>> public key"
curl -sS -o /tmp/auth_public_key.pem -w "%{http_code}" "${AUTH_BASE_URL}/api/auth/v1/auth/public-key" | {
  read -r status
  if [ "${status}" != "200" ]; then
    echo "public key failed (status=${status})" >&2
    cat /tmp/auth_public_key.pem >&2 || true
    exit 1
  fi
}
echo ""

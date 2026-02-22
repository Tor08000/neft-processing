#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[guard][fail] $1" >&2
  exit 1
}

echo "[guard] checking forbidden frontend legacy paths"
if rg -n "/api/core/v1/client|/api/core/v1/partner" frontends/client-portal frontends/partner-portal; then
  fail "Forbidden legacy client/partner API prefixes found in frontend sources"
fi

echo "[guard] checking forbidden non-supported legacy patterns (client/v1, partner/v1)"
if rg -n "/api/core/(client|partner)/v1" frontends docs/audit; then
  fail "Non-supported legacy patterns '/api/core/{client|partner}/v1' found (must not appear)"
fi

echo "[guard] checking gateway config twin alignment"
normalize_gateway() {
  # Remove only full-line comments and empty lines to avoid corrupting values that may contain '#'
  sed '/^[[:space:]]*#/d' "$1" | sed '/^[[:space:]]*$/d'
}
if ! diff -u <(normalize_gateway gateway/nginx.conf) <(normalize_gateway gateway/default.conf) >/tmp/gateway_conf_diff.txt; then
  echo "[guard] normalized diff between gateway/nginx.conf and gateway/default.conf:"
  cat /tmp/gateway_conf_diff.txt
  fail "Gateway config twins are out of sync"
fi

echo "[guard] passed"

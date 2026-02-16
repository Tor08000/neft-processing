#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

if docker compose up --help | grep -q -- '--wait'; then
  docker compose --profile prod up -d --wait
else
  docker compose --profile prod up -d
fi

check_url() {
  local url="$1"
  local name="$2"
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null; then
      echo "healthy: ${name}"
      return 0
    fi
    sleep 2
  done
  echo "healthcheck failed: ${name} (${url})"
  return 1
}

check_url "${BASE_URL}/health" "gateway"
check_url "${BASE_URL}/api/auth/health" "auth-host"
check_url "${BASE_URL}/api/core/health" "core-api"
check_url "${BASE_URL}/partner/" "partner-portal"

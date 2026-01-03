#!/usr/bin/env bash
set -euo pipefail

compose_cmd=(docker compose)

run() {
  local label="$1"; shift
  echo "\n>>> ${label}"
  "${compose_cmd[@]}" exec -T gateway "$@"
}

run "Root redirect" curl -i http://gateway/
run "Admin UI" curl -i http://gateway/admin/
run "Partner UI" curl -i http://gateway/partner/
run "Partner UI deep link" curl -i http://gateway/partner/orders/123
run "Core API health" curl -i http://gateway/api/v1/health
run "Metrics" curl -i http://gateway/metrics

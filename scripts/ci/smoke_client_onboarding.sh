#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CORE_API_BASE_URL:-http://localhost:8080}"

create_response=$(curl -sS -X POST "${BASE_URL}/api/core/client/v1/onboarding/applications" \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke-onboarding@example.com"}')

app_id=$(echo "$create_response" | python -c 'import json,sys; print(json.load(sys.stdin)["application"]["id"])')
access_token=$(echo "$create_response" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -X PUT "${BASE_URL}/api/core/client/v1/onboarding/applications/${app_id}" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${access_token}" \
  -d '{"company_name":"Smoke LLC","inn":"1234567890","org_type":"ООО"}' >/dev/null

curl -sS -X POST "${BASE_URL}/api/core/client/v1/onboarding/applications/${app_id}/submit" \
  -H "Authorization: Bearer ${access_token}" >/dev/null

status=$(curl -sS -X GET "${BASE_URL}/api/core/client/v1/onboarding/applications/${app_id}" \
  -H "Authorization: Bearer ${access_token}" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')

if [[ "$status" != "SUBMITTED" ]]; then
  echo "Expected SUBMITTED, got ${status}"
  exit 1
fi

echo "onboarding smoke passed"

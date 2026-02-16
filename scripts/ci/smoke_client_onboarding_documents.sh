#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CORE_API_BASE_URL:-http://localhost:8080}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

printf '%s' '%PDF-1.7 smoke' > "${TMP_DIR}/sample.pdf"

create_response=$(curl -sS -X POST "${BASE_URL}/api/core/client/v1/onboarding/applications" \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke-onboarding-docs@example.com"}')

app_id=$(echo "$create_response" | python -c 'import json,sys; print(json.load(sys.stdin)["application"]["id"])')
access_token=$(echo "$create_response" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

upload_response=$(curl -sS -X POST "${BASE_URL}/api/core/client/v1/onboarding/applications/${app_id}/documents" \
  -H "Authorization: Bearer ${access_token}" \
  -F 'doc_type=EGRUL' \
  -F "file=@${TMP_DIR}/sample.pdf;type=application/pdf")

doc_id=$(echo "$upload_response" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

list_count=$(curl -sS -X GET "${BASE_URL}/api/core/client/v1/onboarding/applications/${app_id}/documents" \
  -H "Authorization: Bearer ${access_token}" \
  | python -c 'import json,sys; print(len(json.load(sys.stdin)["items"]))')

if [[ "$list_count" -lt 1 ]]; then
  echo "Expected at least one document in list"
  exit 1
fi

http_code=$(curl -sS -o "${TMP_DIR}/downloaded.pdf" -w '%{http_code}' -X GET \
  "${BASE_URL}/api/core/client/v1/onboarding/documents/${doc_id}/download" \
  -H "Authorization: Bearer ${access_token}")

if [[ "$http_code" != "200" ]]; then
  echo "Expected 200 on download, got ${http_code}"
  exit 1
fi

echo "onboarding documents smoke passed"

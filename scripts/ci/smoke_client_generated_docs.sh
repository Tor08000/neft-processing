#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/core/client/v1/onboarding}"
EMAIL="smoke-gen-docs-$(date +%s)@example.com"

app_resp=$(curl -sS -X POST "$BASE_URL/applications" -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\"}")
app_id=$(echo "$app_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["application"]["id"])')
token=$(echo "$app_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST "$BASE_URL/applications/$app_id/generate-docs" -H "Authorization: Bearer $token" >/dev/null
curl -sS "$BASE_URL/applications/$app_id/generated-docs" -H "Authorization: Bearer $token" > /tmp/generated_docs_list.json

doc_id=$(python -c 'import json;print(json.load(open("/tmp/generated_docs_list.json"))["items"][0]["id"])')
content_type=$(curl -sS -D - "$BASE_URL/generated-docs/$doc_id/download" -H "Authorization: Bearer $token" -o /tmp/generated_doc.pdf | tr -d '\r' | awk -F': ' 'tolower($1)=="content-type" {print $2}' | head -n1)

echo "$content_type" | grep -qi 'application/pdf'
echo "smoke_client_generated_docs: ok"

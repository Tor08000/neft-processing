#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/core/client/v1/onboarding}"
EMAIL="smoke-sign-docs-$(date +%s)@example.com"

app_resp=$(curl -sS -X POST "$BASE_URL/applications" -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\"}")
app_id=$(echo "$app_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["application"]["id"])')
token=$(echo "$app_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST "$BASE_URL/applications/$app_id/generate-docs" -H "Authorization: Bearer $token" >/dev/null
curl -sS "$BASE_URL/applications/$app_id/generated-docs" -H "Authorization: Bearer $token" > /tmp/generated_docs_list.json

doc_id=$(python -c 'import json;print(json.load(open("/tmp/generated_docs_list.json"))["items"][0]["id"])')

request_resp=$(curl -sS -X POST "$BASE_URL/generated-docs/$doc_id/sign/request" \
  -H "Authorization: Bearer $token" -H 'content-type: application/json' \
  -d '{"phone":"+79990000000","consent":true}')

request_id=$(echo "$request_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
otp_code=$(echo "$request_resp" | python -c 'import json,sys; print(json.load(sys.stdin).get("otp_code",""))')
if [ -z "$otp_code" ]; then
  echo "otp_code was not returned (requires stub echo in CI)"
  exit 1
fi

confirm_resp=$(curl -sS -X POST "$BASE_URL/generated-docs/$doc_id/sign/confirm" \
  -H "Authorization: Bearer $token" -H 'content-type: application/json' \
  -d "{\"request_id\":\"$request_id\",\"otp_code\":\"$otp_code\"}")

status=$(echo "$confirm_resp" | python -c 'import json,sys; print(json.load(sys.stdin)["doc"]["status"])')
[ "$status" = "SIGNED_BY_CLIENT" ]
echo "smoke_client_doc_signing: ok"

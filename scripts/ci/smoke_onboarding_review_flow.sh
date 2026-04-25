#!/usr/bin/env bash
set -euo pipefail

AUTH_BASE_URL="${AUTH_BASE_URL:-http://localhost}"
CORE_API_BASE_URL="${CORE_API_BASE_URL:-http://localhost:8000}"
ONBOARDING_BASE="${CORE_API_BASE_URL}/api/core/client/v1/onboarding"
ADMIN_REVIEW_BASE="${CORE_API_BASE_URL}/api/core/admin/v1/onboarding"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin@neft.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Neft123!}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

json_field() {
  local file="$1"
  local path="$2"
  python - "$file" "$path" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

cur = data
for part in sys.argv[2].split("."):
    if isinstance(cur, list) and part.isdigit():
        cur = cur[int(part)]
    elif isinstance(cur, dict):
        cur = cur.get(part, "")
    else:
        cur = ""
        break

if isinstance(cur, (dict, list)):
    print(json.dumps(cur))
elif cur is None:
    print("")
else:
    print(cur)
PY
}

create_reviewable_application() {
  local email="smoke-review-$(date +%s%N)@example.com"
  local create_file="${TMP_DIR}/create.json"
  local patch_file="${TMP_DIR}/patch.json"
  local submit_file="${TMP_DIR}/submit.json"
  local sample_pdf="${TMP_DIR}/sample.pdf"
  local status

  printf '%s' '%PDF-1.7 smoke review' > "${sample_pdf}"

  status=$(curl -sS -o "${create_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/applications" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\"}")
  [[ "${status}" == "200" ]] || { echo "create onboarding application failed: ${status}"; cat "${create_file}"; exit 1; }

  APP_ID="$(json_field "${create_file}" "application.id")"
  ONBOARDING_TOKEN="$(json_field "${create_file}" "access_token")"
  [[ -n "${APP_ID}" && -n "${ONBOARDING_TOKEN}" ]] || { echo "missing onboarding application id/token"; cat "${create_file}"; exit 1; }

  status=$(curl -sS -o "${patch_file}" -w '%{http_code}' -X PUT \
    "${ONBOARDING_BASE}/applications/${APP_ID}" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d '{"company_name":"Smoke Review LLC","inn":"7701234567","org_type":"LEGAL","ogrn":"1234567890123"}')
  [[ "${status}" == "200" ]] || { echo "patch onboarding application failed: ${status}"; cat "${patch_file}"; exit 1; }

  for doc_type in CHARTER EGRUL BANK_DETAILS; do
    local upload_file="${TMP_DIR}/upload_${doc_type}.json"
    status=$(curl -sS -o "${upload_file}" -w '%{http_code}' -X POST \
      "${ONBOARDING_BASE}/applications/${APP_ID}/documents" \
      -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
      -F "doc_type=${doc_type}" \
      -F "file=@${sample_pdf};type=application/pdf")
    [[ "${status}" == "201" ]] || { echo "upload ${doc_type} failed: ${status}"; cat "${upload_file}"; exit 1; }
  done

  status=$(curl -sS -o "${submit_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/applications/${APP_ID}/submit" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "submit onboarding application failed: ${status}"; cat "${submit_file}"; exit 1; }
}

fetch_admin_token() {
  local login_file="${TMP_DIR}/admin_login.json"
  local status

  status=$(curl -sS -o "${login_file}" -w '%{http_code}' -X POST \
    "${AUTH_BASE_URL}/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"login\":\"${ADMIN_LOGIN}\",\"password\":\"${ADMIN_PASSWORD}\",\"portal\":\"admin\"}")
  [[ "${status}" == "200" ]] || { echo "admin login failed: ${status}"; cat "${login_file}"; exit 1; }

  ADMIN_TOKEN="$(json_field "${login_file}" "access_token")"
  [[ -n "${ADMIN_TOKEN}" ]] || { echo "missing admin token"; cat "${login_file}"; exit 1; }
}

create_reviewable_application
fetch_admin_token

start_file="${TMP_DIR}/start_review.json"
start_status=$(curl -sS -o "${start_file}" -w '%{http_code}' -X POST \
  "${ADMIN_REVIEW_BASE}/applications/${APP_ID}/start-review" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")
[[ "${start_status}" == "200" ]] || { echo "start review failed: ${start_status}"; cat "${start_file}"; exit 1; }

detail_file="${TMP_DIR}/review_detail.json"
detail_status=$(curl -sS -o "${detail_file}" -w '%{http_code}' \
  "${ADMIN_REVIEW_BASE}/applications/${APP_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")
[[ "${detail_status}" == "200" ]] || { echo "review detail failed: ${detail_status}"; cat "${detail_file}"; exit 1; }

python - "${detail_file}" > "${TMP_DIR}/review_doc_ids.txt" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)

docs = payload.get("documents") or []
if len(docs) < 3:
    raise SystemExit("expected at least 3 uploaded documents before review")

for doc in docs:
    print(doc["id"])
PY

while IFS= read -r doc_id; do
  [[ -n "${doc_id}" ]] || continue
  verify_file="${TMP_DIR}/verify_${doc_id}.json"
  verify_status=$(curl -sS -o "${verify_file}" -w '%{http_code}' -X POST \
    "${ADMIN_REVIEW_BASE}/documents/${doc_id}/verify" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d '{"comment":"ok"}')
  [[ "${verify_status}" == "200" ]] || { echo "verify document ${doc_id} failed: ${verify_status}"; cat "${verify_file}"; exit 1; }
done < "${TMP_DIR}/review_doc_ids.txt"

echo "smoke_onboarding_review_flow: ok"

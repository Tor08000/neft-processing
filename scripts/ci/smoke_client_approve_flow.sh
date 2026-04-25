#!/usr/bin/env bash
set -euo pipefail

AUTH_BASE_URL="${AUTH_BASE_URL:-http://localhost}"
CORE_API_BASE_URL="${CORE_API_BASE_URL:-http://localhost:8000}"
ONBOARDING_BASE="${CORE_API_BASE_URL}/api/core/client/v1/onboarding"
ADMIN_REVIEW_BASE="${CORE_API_BASE_URL}/api/core/admin/v1/onboarding"
CLIENT_ME_URL="${CORE_API_BASE_URL}/api/core/client/v1/me"
PORTAL_ME_URL="${CORE_API_BASE_URL}/api/core/portal/me"
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
  local email="smoke-approve-$(date +%s%N)@example.com"
  local create_file="${TMP_DIR}/create.json"
  local patch_file="${TMP_DIR}/patch.json"
  local submit_file="${TMP_DIR}/submit.json"
  local sample_pdf="${TMP_DIR}/sample.pdf"
  local status

  printf '%s' '%PDF-1.7 smoke approve' > "${sample_pdf}"

  status=$(curl -sS -o "${create_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/applications" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\"}")
  [[ "${status}" == "200" ]] || { echo "create onboarding application failed: ${status}"; cat "${create_file}"; exit 1; }

  APP_ID="$(json_field "${create_file}" "application.id")"
  ONBOARDING_TOKEN="$(json_field "${create_file}" "access_token")"
  COMPANY_NAME="Smoke Approve LLC $(date +%s)"
  [[ -n "${APP_ID}" && -n "${ONBOARDING_TOKEN}" ]] || { echo "missing onboarding application id/token"; cat "${create_file}"; exit 1; }

  status=$(curl -sS -o "${patch_file}" -w '%{http_code}' -X PUT \
    "${ONBOARDING_BASE}/applications/${APP_ID}" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d "{\"company_name\":\"${COMPANY_NAME}\",\"inn\":\"7701234567\",\"org_type\":\"LEGAL\",\"ogrn\":\"1234567890123\"}")
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

start_and_verify_review() {
  local start_file="${TMP_DIR}/start_review.json"
  local detail_file="${TMP_DIR}/review_detail.json"
  local doc_ids_file="${TMP_DIR}/review_doc_ids.txt"
  local status

  status=$(curl -sS -o "${start_file}" -w '%{http_code}' -X POST \
    "${ADMIN_REVIEW_BASE}/applications/${APP_ID}/start-review" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "start review failed: ${status}"; cat "${start_file}"; exit 1; }

  status=$(curl -sS -o "${detail_file}" -w '%{http_code}' \
    "${ADMIN_REVIEW_BASE}/applications/${APP_ID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "review detail failed: ${status}"; cat "${detail_file}"; exit 1; }

  python - "${detail_file}" > "${doc_ids_file}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)

docs = payload.get("documents") or []
if len(docs) < 3:
    raise SystemExit("expected at least 3 uploaded documents before approval")

for doc in docs:
    print(doc["id"])
PY
}

verify_doc() {
  local doc_id="$1"
  local verify_file="${TMP_DIR}/verify_${doc_id}.json"
  local status

  status=$(curl -sS -o "${verify_file}" -w '%{http_code}' -X POST \
    "${ADMIN_REVIEW_BASE}/documents/${doc_id}/verify" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d '{"comment":"ok"}')
  [[ "${status}" == "200" ]] || { echo "verify document ${doc_id} failed: ${status}"; cat "${verify_file}"; exit 1; }
}

create_reviewable_application
fetch_admin_token

start_and_verify_review

while IFS= read -r doc_id; do
  [[ -n "${doc_id}" ]] || continue
  verify_doc "${doc_id}"
done < "${TMP_DIR}/review_doc_ids.txt"

approve_file="${TMP_DIR}/approve.json"
approve_status=$(curl -sS -o "${approve_file}" -w '%{http_code}' -X POST \
  "${ADMIN_REVIEW_BASE}/applications/${APP_ID}/approve" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"comment":"approved"}')
[[ "${approve_status}" == "200" ]] || { echo "approve onboarding application failed: ${approve_status}"; cat "${approve_file}"; exit 1; }

APPROVED_STATUS="$(json_field "${approve_file}" "status")"
[[ "${APPROVED_STATUS}" == "APPROVED" ]] || { echo "expected APPROVED status, got ${APPROVED_STATUS}"; cat "${approve_file}"; exit 1; }

decision_file="${TMP_DIR}/decision.json"
decision_status=$(curl -sS -o "${decision_file}" -w '%{http_code}' \
  "${ONBOARDING_BASE}/my-application/decision" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${decision_status}" == "200" ]] || { echo "decision lookup failed: ${decision_status}"; cat "${decision_file}"; exit 1; }
[[ "$(json_field "${decision_file}" "status")" == "APPROVED" ]] || { echo "expected client decision APPROVED"; cat "${decision_file}"; exit 1; }

issue_file="${TMP_DIR}/issue_client_token.json"
issue_status=$(curl -sS -o "${issue_file}" -w '%{http_code}' -X POST \
  "${ONBOARDING_BASE}/my-application/issue-client-token" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${issue_status}" == "200" ]] || { echo "issue client token failed: ${issue_status}"; cat "${issue_file}"; exit 1; }

CLIENT_TOKEN="$(json_field "${issue_file}" "access_token")"
[[ -n "${CLIENT_TOKEN}" ]] || { echo "missing client token"; cat "${issue_file}"; exit 1; }

client_me_file="${TMP_DIR}/client_me.json"
client_me_status=$(curl -sS -o "${client_me_file}" -w '%{http_code}' \
  "${CLIENT_ME_URL}" \
  -H "Authorization: Bearer ${CLIENT_TOKEN}")
[[ "${client_me_status}" == "200" ]] || { echo "client me failed: ${client_me_status}"; cat "${client_me_file}"; exit 1; }

portal_me_file="${TMP_DIR}/portal_me.json"
portal_me_status=$(curl -sS -o "${portal_me_file}" -w '%{http_code}' \
  "${PORTAL_ME_URL}" \
  -H "Authorization: Bearer ${CLIENT_TOKEN}")
[[ "${portal_me_status}" == "200" ]] || { echo "portal/me failed: ${portal_me_status}"; cat "${portal_me_file}"; exit 1; }

python - "${portal_me_file}" "${COMPANY_NAME}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)

org = payload.get("org") or {}
if org.get("name") != sys.argv[2]:
    raise SystemExit(f"unexpected org name: {org.get('name')!r}")
PY

echo "smoke_client_approve_flow: ok"

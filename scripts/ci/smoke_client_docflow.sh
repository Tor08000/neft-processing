#!/usr/bin/env bash
set -euo pipefail

AUTH_BASE_URL="${AUTH_BASE_URL:-http://localhost}"
CORE_API_BASE_URL="${CORE_API_BASE_URL:-http://localhost:8000}"
ONBOARDING_BASE="${CORE_API_BASE_URL}/api/core/client/v1/onboarding"
DOCFLOW_BASE="${CORE_API_BASE_URL}/api/core/client/docflow"
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
  local email="smoke-docflow-$(date +%s%N)@example.com"
  local create_file="${TMP_DIR}/create.json"
  local patch_file="${TMP_DIR}/patch.json"
  local submit_file="${TMP_DIR}/submit.json"
  local sample_pdf="${TMP_DIR}/sample.pdf"
  local status

  printf '%s' '%PDF-1.7 smoke docflow' > "${sample_pdf}"

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
    -d '{"company_name":"Smoke Docflow LLC","inn":"7701234567","org_type":"LEGAL","ogrn":"1234567890123"}')
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

start_review() {
  local start_file="${TMP_DIR}/start_review.json"
  local status

  status=$(curl -sS -o "${start_file}" -w '%{http_code}' -X POST \
    "${ADMIN_REVIEW_BASE}/applications/${APP_ID}/start-review" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "start review failed: ${status}"; cat "${start_file}"; exit 1; }
}

generate_and_sign_doc() {
  local generate_file="${TMP_DIR}/generate_docs.json"
  local list_file="${TMP_DIR}/generated_docs.json"
  local start_file="${TMP_DIR}/otp_start.json"
  local confirm_file="${TMP_DIR}/otp_confirm.json"
  local status

  status=$(curl -sS -o "${generate_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/applications/${APP_ID}/generate-docs" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "generate docs failed: ${status}"; cat "${generate_file}"; exit 1; }

  status=$(curl -sS -o "${list_file}" -w '%{http_code}' \
    "${ONBOARDING_BASE}/applications/${APP_ID}/generated-docs" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
  [[ "${status}" == "200" ]] || { echo "list generated docs failed: ${status}"; cat "${list_file}"; exit 1; }

  DOC_ID="$(json_field "${list_file}" "items.0.id")"
  [[ -n "${DOC_ID}" ]] || { echo "missing generated doc id"; cat "${list_file}"; exit 1; }

  status=$(curl -sS -o "${start_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/generated-docs/${DOC_ID}/sign/otp/start" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d '{"channel":"sms","destination":"+79990000000"}')
  [[ "${status}" == "200" ]] || { echo "otp start failed: ${status}"; cat "${start_file}"; exit 1; }

  CHALLENGE_ID="$(json_field "${start_file}" "challenge_id")"
  OTP_CODE="$(json_field "${start_file}" "otp_code")"
  [[ -n "${CHALLENGE_ID}" && -n "${OTP_CODE}" ]] || { echo "missing challenge_id or otp_code"; cat "${start_file}"; exit 1; }

  status=$(curl -sS -o "${confirm_file}" -w '%{http_code}' -X POST \
    "${ONBOARDING_BASE}/generated-docs/${DOC_ID}/sign/otp/confirm" \
    -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d "{\"challenge_id\":\"${CHALLENGE_ID}\",\"code\":\"${OTP_CODE}\"}")
  [[ "${status}" == "200" ]] || { echo "otp confirm failed: ${status}"; cat "${confirm_file}"; exit 1; }

  [[ "$(json_field "${confirm_file}" "doc.status")" == "SIGNED_BY_CLIENT" ]] || { echo "expected SIGNED_BY_CLIENT"; cat "${confirm_file}"; exit 1; }
}

create_reviewable_application
fetch_admin_token
start_review
generate_and_sign_doc

timeline_file="${TMP_DIR}/timeline.json"
timeline_status=$(curl -sS -o "${timeline_file}" -w '%{http_code}' \
  "${DOCFLOW_BASE}/timeline?application_id=${APP_ID}" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${timeline_status}" == "200" ]] || { echo "timeline fetch failed: ${timeline_status}"; cat "${timeline_file}"; exit 1; }

python - "${timeline_file}" "${DOC_ID}" "${APP_ID}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    items = (json.load(fh).get("items") or [])

doc_id = sys.argv[2]
app_id = sys.argv[3]
if not any(item.get("event_type") == "DOC_SIGNED_BY_CLIENT" and item.get("doc_id") == doc_id and item.get("application_id") == app_id for item in items):
    raise SystemExit("timeline does not contain DOC_SIGNED_BY_CLIENT for the expected document")
PY

package_create_file="${TMP_DIR}/package_create.json"
package_status=$(curl -sS -o "${package_create_file}" -w '%{http_code}' -X POST \
  "${DOCFLOW_BASE}/packages" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"application_id\":\"${APP_ID}\",\"doc_ids\":[\"${DOC_ID}\"]}")
[[ "${package_status}" == "200" ]] || { echo "package create failed: ${package_status}"; cat "${package_create_file}"; exit 1; }

PACKAGE_ID="$(json_field "${package_create_file}" "id")"
[[ "$(json_field "${package_create_file}" "status")" == "READY" ]] || { echo "expected READY package"; cat "${package_create_file}"; exit 1; }
[[ -n "${PACKAGE_ID}" ]] || { echo "missing package id"; cat "${package_create_file}"; exit 1; }

package_list_file="${TMP_DIR}/packages.json"
package_list_status=$(curl -sS -o "${package_list_file}" -w '%{http_code}' \
  "${DOCFLOW_BASE}/packages?application_id=${APP_ID}" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${package_list_status}" == "200" ]] || { echo "packages list failed: ${package_list_status}"; cat "${package_list_file}"; exit 1; }

python - "${package_list_file}" "${PACKAGE_ID}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    items = (json.load(fh).get("items") or [])

if not any(item.get("id") == sys.argv[2] for item in items):
    raise SystemExit("package id not present in package list")
PY

download_file="${TMP_DIR}/package.zip"
download_status=$(curl -sS -o "${download_file}" -w '%{http_code}' \
  "${DOCFLOW_BASE}/packages/${PACKAGE_ID}/download" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${download_status}" == "200" ]] || { echo "package download failed: ${download_status}"; exit 1; }

python - "${download_file}" <<'PY'
import io
import sys
import zipfile

with open(sys.argv[1], "rb") as fh:
    archive = zipfile.ZipFile(io.BytesIO(fh.read()))
    names = set(archive.namelist())

if not any(name.startswith("outbound/") for name in names):
    raise SystemExit("expected outbound/ payloads in package zip")
if not any(name.startswith("signatures/") for name in names):
    raise SystemExit("expected signatures/ payloads in package zip")
PY

notifications_file="${TMP_DIR}/notifications.json"
notifications_status=$(curl -sS -o "${notifications_file}" -w '%{http_code}' \
  "${DOCFLOW_BASE}/notifications" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${notifications_status}" == "200" ]] || { echo "notifications list failed: ${notifications_status}"; cat "${notifications_file}"; exit 1; }

NOTIFICATION_ID="$(python - "${notifications_file}" "${DOC_ID}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)

items = payload.get("items") or []
if payload.get("unread_count", 0) < 1:
    raise SystemExit("expected unread notifications after doc signing")

for item in items:
    if item.get("kind") == "DOC_SIGNED_BY_CLIENT" and (item.get("payload") or {}).get("doc_id") == sys.argv[2]:
        print(item["id"])
        break
else:
    raise SystemExit("expected DOC_SIGNED_BY_CLIENT notification for signed document")
PY
)"

read_file="${TMP_DIR}/notification_read.json"
read_status=$(curl -sS -o "${read_file}" -w '%{http_code}' -X POST \
  "${DOCFLOW_BASE}/notifications/${NOTIFICATION_ID}/read" \
  -H "Authorization: Bearer ${ONBOARDING_TOKEN}")
[[ "${read_status}" == "200" ]] || { echo "notification read failed: ${read_status}"; cat "${read_file}"; exit 1; }
[[ -n "$(json_field "${read_file}" "read_at")" ]] || { echo "expected read_at after marking notification read"; cat "${read_file}"; exit 1; }

echo "smoke_client_docflow: ok"

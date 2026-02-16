#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CORE_API_BASE_URL:-http://localhost:8080}"
TOKEN="${CLIENT_SMOKE_TOKEN:-}"
INVITE_EMAIL="smoke.client.invite.resend.revoke@example.com"

if [[ -z "${TOKEN}" ]]; then
  echo "[smoke_client_invitation_resend_revoke] CLIENT_SMOKE_TOKEN is not set; skipping smoke run"
  exit 0
fi

invite_status=$(curl -sS -o /tmp/client_invite_resend_revoke_invite.json -w "%{http_code}" \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"email\":\"${INVITE_EMAIL}\",\"roles\":[\"CLIENT_MANAGER\"]}" \
  "${BASE_URL}/api/core/client/users/invite")
if [[ "${invite_status}" != "201" && "${invite_status}" != "409" ]]; then
  echo "invite failed: ${invite_status}"; cat /tmp/client_invite_resend_revoke_invite.json; exit 1
fi

list_status=$(curl -sS -o /tmp/client_invite_resend_revoke_list.json -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  "${BASE_URL}/api/core/client/users/invitations")
[[ "${list_status}" == "200" ]]

invitation_id=$(python - <<'PY'
import json
with open('/tmp/client_invite_resend_revoke_list.json','r',encoding='utf-8') as f:
    data=json.load(f)
for item in data.get('items',[]):
    if item.get('email')=='smoke.client.invite.resend.revoke@example.com' and item.get('status')=='PENDING':
        print(item.get('invitation_id'))
        break
PY
)

if [[ -z "${invitation_id}" ]]; then
  echo "no pending invitation found"; cat /tmp/client_invite_resend_revoke_list.json; exit 1
fi

resend_status=$(curl -sS -o /tmp/client_invite_resend_revoke_resend.json -w "%{http_code}" \
  -X POST -H 'Content-Type: application/json' -H "Authorization: Bearer ${TOKEN}" \
  -d '{"expires_in_days":7}' \
  "${BASE_URL}/api/core/client/users/invitations/${invitation_id}/resend")
[[ "${resend_status}" == "200" ]]

revoke_status=$(curl -sS -o /tmp/client_invite_resend_revoke_revoke.json -w "%{http_code}" \
  -X POST -H 'Content-Type: application/json' -H "Authorization: Bearer ${TOKEN}" \
  -d '{"reason":"smoke"}' \
  "${BASE_URL}/api/core/client/users/invitations/${invitation_id}/revoke")
[[ "${revoke_status}" == "200" ]]

revoke_again_status=$(curl -sS -o /tmp/client_invite_resend_revoke_revoke_again.json -w "%{http_code}" \
  -X POST -H "Authorization: Bearer ${TOKEN}" \
  "${BASE_URL}/api/core/client/users/invitations/${invitation_id}/revoke")
[[ "${revoke_again_status}" == "409" ]]

echo "client invitation resend/revoke smoke passed"

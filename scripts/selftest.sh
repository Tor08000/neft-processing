#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

DC=${DOCKER_COMPOSE:-"docker compose"}
BASE_URL=${SELFTEST_BASE_URL:-"http://localhost"}

ADMIN_EMAIL=${NEFT_BOOTSTRAP_ADMIN_EMAIL:-admin@neft.local}
ADMIN_PASSWORD=${NEFT_BOOTSTRAP_ADMIN_PASSWORD:-admin}
CLIENT_EMAIL=${NEFT_BOOTSTRAP_CLIENT_EMAIL:-client@neft.local}
CLIENT_PASSWORD=${NEFT_BOOTSTRAP_CLIENT_PASSWORD:-client}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

step() {
  echo "\n[selftest] $1"
}

http_status() {
  local method="$1"; shift
  local url="$1"; shift
  local out_file="$1"; shift
  local data="${1:-}"
  if [ -n "$data" ]; then
    curl -sS -o "$out_file" -w "%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" -d "$data"
  else
    curl -sS -o "$out_file" -w "%{http_code}" -X "$method" "$url"
  fi
}

extract_json_field() {
  local file="$1"
  local field="$2"
  python - "$file" "$field" <<'PY'
import json, sys
path, field = sys.argv[1], sys.argv[2]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
val = data
for part in field.split('.'):
    if isinstance(val, dict):
        val = val.get(part)
    else:
        val = None
        break
if val is None:
    sys.exit(2)
print(val)
PY
}

extract_token() {
  local file="$1"
  python - "$file" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('access_token') or data.get('token') or '')
PY
}

step "Starting containers"
$DC up -d --build

step "Checking compose services status"
$DC ps --format json > "$TMP_DIR/ps.jsonl"
python - "$TMP_DIR/ps.jsonl" <<'PY'
import json, sys
bad = []
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        state = (obj.get('State') or '').lower()
        if state not in {'running', 'restarting'}:
            bad.append((obj.get('Service') or obj.get('Name'), state))
if bad:
    for name, state in bad:
        print(f"service not healthy state: {name} -> {state}")
    sys.exit(1)
PY

step "Health checks: gateway/auth/core"
for path in /health /api/auth/health /api/core/health; do
  code=$(http_status GET "${BASE_URL}${path}" "$TMP_DIR/health.json")
  if [ "$code" != "200" ]; then
    echo "health check failed for ${path}: status=${code}"
    cat "$TMP_DIR/health.json"
    exit 1
  fi
done

step "Gateway routing smoke for auth/core namespaces"
code=$(http_status POST "${BASE_URL}/api/auth/v1/auth/login" "$TMP_DIR/login_invalid.json" '{"email":"invalid@example.com","password":"invalid","portal":"admin"}')
if [ "$code" != "401" ]; then
  echo "unexpected status from auth login through gateway: ${code}"
  cat "$TMP_DIR/login_invalid.json"
  exit 1
fi
code=$(http_status GET "${BASE_URL}/api/core/health" "$TMP_DIR/core_health.json")
if [ "$code" != "200" ]; then
  echo "unexpected status from core health through gateway: ${code}"
  cat "$TMP_DIR/core_health.json"
  exit 1
fi

step "Seeded admin login + auth me"
admin_payload=$(printf '{"email":"%s","password":"%s","portal":"admin"}' "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
code=$(http_status POST "${BASE_URL}/api/auth/v1/auth/login" "$TMP_DIR/admin_login.json" "$admin_payload")
if [ "$code" != "200" ]; then
  echo "admin login failed: status=${code}"
  cat "$TMP_DIR/admin_login.json"
  exit 1
fi
ADMIN_TOKEN=$(extract_token "$TMP_DIR/admin_login.json")
[ -n "$ADMIN_TOKEN" ] || { echo "empty admin token"; exit 1; }
curl -sS -o "$TMP_DIR/auth_me.json" -w "%{http_code}" "${BASE_URL}/api/auth/v1/auth/me" -H "Authorization: Bearer ${ADMIN_TOKEN}" | grep -qx '200'

step "Seeded client login + profile/modules/permissions"
client_payload=$(printf '{"email":"%s","password":"%s","portal":"client"}' "$CLIENT_EMAIL" "$CLIENT_PASSWORD")
code=$(http_status POST "${BASE_URL}/api/auth/v1/auth/login" "$TMP_DIR/client_login.json" "$client_payload")
if [ "$code" != "200" ]; then
  echo "client login failed: status=${code}"
  cat "$TMP_DIR/client_login.json"
  exit 1
fi
CLIENT_TOKEN=$(extract_token "$TMP_DIR/client_login.json")
[ -n "$CLIENT_TOKEN" ] || { echo "empty client token"; exit 1; }
code=$(curl -sS -o "$TMP_DIR/client_me.json" -w "%{http_code}" "${BASE_URL}/api/core/client/api/v1/client/me" -H "Authorization: Bearer ${CLIENT_TOKEN}")
if [ "$code" != "200" ]; then
  echo "client me failed: status=${code}"
  cat "$TMP_DIR/client_me.json"
  exit 1
fi
extract_json_field "$TMP_DIR/client_me.json" "enabled_modules" >/dev/null
extract_json_field "$TMP_DIR/client_me.json" "permissions" >/dev/null

step "Manager flow: admin creates employee in auth-host"
NEW_USER_EMAIL="selftest.$(date +%s)@neft.local"
NEW_USER_PASSWORD="ChangeMe123!"
create_payload=$(printf '{"email":"%s","password":"%s","roles":["CLIENT_MANAGER"],"full_name":"Selftest Employee"}' "$NEW_USER_EMAIL" "$NEW_USER_PASSWORD")
code=$(curl -sS -o "$TMP_DIR/create_user.json" -w "%{http_code}" -X POST "${BASE_URL}/api/auth/v1/admin/users" -H "Authorization: Bearer ${ADMIN_TOKEN}" -H "Content-Type: application/json" -d "$create_payload")
if [ "$code" != "201" ]; then
  echo "admin create user failed: status=${code}"
  cat "$TMP_DIR/create_user.json"
  exit 1
fi

step "Employee login + core lookup should not return 500"
new_payload=$(printf '{"email":"%s","password":"%s","portal":"client"}' "$NEW_USER_EMAIL" "$NEW_USER_PASSWORD")
code=$(http_status POST "${BASE_URL}/api/auth/v1/auth/login" "$TMP_DIR/new_login.json" "$new_payload")
if [ "$code" != "200" ]; then
  echo "new user login failed: status=${code}"
  cat "$TMP_DIR/new_login.json"
  exit 1
fi
NEW_TOKEN=$(extract_token "$TMP_DIR/new_login.json")
code=$(curl -sS -o "$TMP_DIR/new_client_me.json" -w "%{http_code}" "${BASE_URL}/api/core/client/api/v1/client/me" -H "Authorization: Bearer ${NEW_TOKEN}")
if [ "$code" -ge 500 ]; then
  echo "core lookup returned server error for new user: status=${code}"
  cat "$TMP_DIR/new_client_me.json"
  exit 1
fi

step "Migration smoke on clean DB (ephemeral)"
$DC -f docker-compose.test.yml run --rm core-api pytest -q app/tests/test_schema_smoke.py

echo "\n[selftest] OK"

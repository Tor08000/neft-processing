#!/usr/bin/env bash
# Simple smoke test to ensure local docker-compose stack is alive.
set -euo pipefail

DC_BIN="${DOCKER_COMPOSE:-docker compose}"
POSTGRES_DB="${POSTGRES_DB:-neft}"
POSTGRES_USER="${POSTGRES_USER:-neft}"
TABLES_FILE="${TABLES_FILE:-scripts/expected_tables.txt}"

info() { echo "[smoke] $*"; }

table_exists() {
    local table="$1"
    ${DC_BIN} exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
        "select to_regclass('public.${table}')"
}

check_url() {
    local name="$1"
    local url="$2"
    local allowed_codes="${3:-200 201 202 204 301 302 304}"

    local code
    code=$(curl -ks -o /dev/null -w "%{http_code}" "$url")

    if echo "$allowed_codes" | grep -q "\b${code}\b"; then
        info "$name ok (status ${code})"
    else
        echo "[smoke][ERROR] $name failed with status ${code}" >&2
        exit 1
    fi
}

info "docker compose ps"
${DC_BIN} ps

if [[ ! -f "${TABLES_FILE}" ]]; then
    echo "[smoke][ERROR] expected tables file not found: ${TABLES_FILE}" >&2
    exit 1
fi

info "checking expected tables"
while IFS= read -r table; do
    [[ -z "${table}" || "${table}" =~ ^# ]] && continue
    exists=$(table_exists "${table}" | tr -d '[:space:]')
    if [[ -z "${exists}" || "${exists}" == "null" ]]; then
        echo "[smoke][ERROR] missing table: ${table}" >&2
        exit 1
    fi
    info "table ${table} exists"
done < "${TABLES_FILE}"

info "health endpoints via gateway"
check_url "gateway health" "http://localhost/health"
check_url "core-api health" "http://localhost/api/v1/health"
check_url "admin web" "http://localhost/admin/" "200 301 302 304"
check_url "client web" "http://localhost/client/" "200 301 302 304"

info "smoke test finished"

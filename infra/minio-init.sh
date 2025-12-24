#!/bin/sh

set -e

log() {
  echo "[minio-init] $1"
}

require_var() {
  var_name="$1"
  var_value="$(eval echo \$$var_name)"

  if [ -z "$var_value" ]; then
    log "ERROR: $var_name is not set"
    exit 1
  fi
}

require_var MINIO_ROOT_USER
require_var MINIO_ROOT_PASSWORD
require_var NEFT_S3_ACCESS_KEY
require_var NEFT_S3_SECRET_KEY

ALIAS_NAME="local"
ENDPOINT="${MINIO_ENDPOINT:-${NEFT_S3_ENDPOINT:-http://minio:9000}}"
ACCESS_KEY="${MINIO_ROOT_USER}"
SECRET_KEY="${MINIO_ROOT_PASSWORD}"
BUCKET_MAIN="${NEFT_S3_BUCKET:-neft}"
BUCKET_INVOICES="${NEFT_S3_BUCKET_INVOICES:-neft-invoices}"
BUCKET_PAYOUTS="${NEFT_S3_BUCKET_PAYOUTS:-neft-payouts}"
S3_ACCESS_KEY="${NEFT_S3_ACCESS_KEY}"
S3_SECRET_KEY="${NEFT_S3_SECRET_KEY}"
MAX_RETRIES="${MINIO_INIT_RETRIES:-60}"
SLEEP_SECONDS="${MINIO_INIT_RETRY_DELAY:-2}"

wait_for_minio() {
  attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    if mc alias set "$ALIAS_NAME" "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY" >/dev/null 2>&1; then
      log "connected to MinIO after $attempt attempt(s)"
      return 0
    fi
    log "MinIO unavailable (attempt $attempt/$MAX_RETRIES), retrying in ${SLEEP_SECONDS}s..."
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done

  log "failed to connect to MinIO after $MAX_RETRIES attempts"
  return 1
}

ensure_bucket() {
  bucket="$1"

  if [ -z "$bucket" ]; then
    return
  fi

  log "ensuring bucket '$bucket' exists"
  mc mb --ignore-existing "$ALIAS_NAME/$bucket"

  log "enabling versioning for '$bucket'"
  mc version enable "$ALIAS_NAME/$bucket"

  log "enforcing private policy for '$bucket'"
  mc anonymous set none "$ALIAS_NAME/$bucket"
}

if ! command -v mc >/dev/null 2>&1; then
  log "mc binary not found"
  exit 1
fi

wait_for_minio
mc alias set "$ALIAS_NAME" "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY"

ensure_bucket "$BUCKET_MAIN"
if [ "$BUCKET_INVOICES" != "$BUCKET_MAIN" ]; then
  ensure_bucket "$BUCKET_INVOICES"
fi
if [ "$BUCKET_PAYOUTS" != "$BUCKET_MAIN" ] && [ "$BUCKET_PAYOUTS" != "$BUCKET_INVOICES" ]; then
  ensure_bucket "$BUCKET_PAYOUTS"
fi

log "running smoke check: listing buckets and fetching admin info"
mc ls "$ALIAS_NAME" >/dev/null 2>&1
mc admin info "$ALIAS_NAME" >/dev/null 2>&1

log "init complete"

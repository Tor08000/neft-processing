#!/bin/sh

set -e

ALIAS_NAME="local"
ENDPOINT="${MINIO_ENDPOINT:-${NEFT_S3_ENDPOINT:-http://minio:9000}}"
ACCESS_KEY="${MINIO_ROOT_USER:-neftminio}"
SECRET_KEY="${MINIO_ROOT_PASSWORD:-neftminiosecret}"
BUCKET_MAIN="${NEFT_S3_BUCKET:-neft}"
BUCKET_INVOICES="${NEFT_S3_BUCKET_INVOICES:-neft-invoices}"
PUBLIC_MAIN="${NEFT_S3_BUCKET_PUBLIC:-0}"
PUBLIC_INVOICES="${NEFT_S3_BUCKET_INVOICES_PUBLIC:-0}"
MAX_RETRIES="${MINIO_INIT_RETRIES:-60}"
SLEEP_SECONDS="${MINIO_INIT_RETRY_DELAY:-2}"

log() {
  echo "[minio-init] $1"
}

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
  public_flag="$2"

  if [ -z "$bucket" ]; then
    return
  fi

  log "ensuring bucket '$bucket' exists"
  mc mb --ignore-existing "$ALIAS_NAME/$bucket" >/dev/null 2>&1 || true

  log "enabling versioning for '$bucket'"
  mc version enable "$ALIAS_NAME/$bucket" >/dev/null 2>&1 || true

  if [ "$public_flag" = "1" ]; then
    log "setting public download policy for '$bucket'"
    mc anonymous set download "$ALIAS_NAME/$bucket" >/dev/null 2>&1 || true
  else
    log "enforcing private policy for '$bucket'"
    mc anonymous set none "$ALIAS_NAME/$bucket" >/dev/null 2>&1 || true
  fi
}

if ! command -v mc >/dev/null 2>&1; then
  log "mc binary not found"
  exit 1
fi

wait_for_minio

ensure_bucket "$BUCKET_MAIN" "$PUBLIC_MAIN"
if [ "$BUCKET_INVOICES" != "$BUCKET_MAIN" ]; then
  ensure_bucket "$BUCKET_INVOICES" "$PUBLIC_INVOICES"
fi

log "running smoke check: listing buckets and fetching admin info"
if ! mc ls "$ALIAS_NAME" >/dev/null 2>&1; then
  log "failed to list buckets via alias '$ALIAS_NAME'"
  exit 1
fi

if ! mc admin info "$ALIAS_NAME" >/dev/null 2>&1; then
  log "failed to fetch admin info via alias '$ALIAS_NAME'"
  exit 1
fi

log "init complete"

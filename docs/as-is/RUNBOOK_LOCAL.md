# NEFT Platform — Local Runbook (AS-IS, Windows CMD)

> **Scope:** local compose stack defined in `docker-compose.yml`.

## 1) Prerequisites

- Docker Desktop / Docker Engine installed.
- Ports available: `80`, `3000`, `4173`, `4174`, `4175`, `5432`, `6379`, `8001`, `8002`, `8003`, `8010`, `5555`, `9000`, `9001`, `9090`, `16686`, `3100`, `9080`, `4317`.

## 2) Configure environment

```cmd
copy .env.example .env
```

Edit `.env` and set at least:
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `NEFT_S3_ACCESS_KEY`, `NEFT_S3_SECRET_KEY`
- `POSTGRES_PASSWORD`

(See `.env.example` for full list.)

## 3) Start the stack

```cmd
docker compose up -d --build
```

## 4) Apply DB migrations (core-api)

```cmd
scripts\migrate.cmd
```

Auth-host migrations are handled by its own service start; if needed:

```cmd
docker compose exec -T auth-host sh -lc "alembic -c alembic.ini upgrade head"
```

## 5) Health checks (HTTP)

Gateway + APIs:

```cmd
curl http://localhost/health
curl http://localhost/api/core/health
curl http://localhost/api/auth/health
curl http://localhost/api/ai/health
curl http://localhost/api/int/health
```

Direct service ports:

```cmd
curl http://localhost:8001/api/core/health
curl http://localhost:8002/api/auth/health
curl http://localhost:8003/api/v1/health
curl http://localhost:8010/health
```

Frontends:

```cmd
curl http://localhost:4173/health
curl http://localhost:4174/health
curl http://localhost:4175/health
```

Observability:

```cmd
curl http://localhost:9090/-/healthy
curl http://localhost:3000/health
curl http://localhost:16686/
```

## 6) Metrics checks

```cmd
curl http://localhost/metrics
curl http://localhost:8001/metrics
curl http://localhost:8003/metrics
curl http://localhost:8010/metrics
curl http://localhost:9808/metrics
```

## 7) Logs

```cmd
docker compose logs -f core-api
docker compose logs -f auth-host
docker compose logs -f integration-hub
docker compose logs -f gateway
```

## 8) Common tasks (CMD helpers)

```cmd
scripts\get_admin_token.cmd
scripts\test_core_api.cmd
scripts\test_processing_core.cmd
scripts\test_core_stack.cmd
scripts\test_auth_host.cmd
scripts\billing_smoke.cmd
scripts\smoke_billing_v14.cmd
scripts\smoke_invoice_state_machine.cmd
scripts\smoke_legal_gate.cmd
```

**Processing-core tests (recommended):**
```cmd
scripts\test_core_stack.cmd
scripts\test_core_stack.cmd --full
```

Processing-core tests are run inside docker compose; host runs are not supported.

## 9) Known failure points

1) **MinIO not initialized** → check `minio-health` and `minio-init` logs. (`infra/minio-init.sh`)
2) **Auth-host fails to start** → verify key paths and `AUTH_KEY_DIR` volume. (`docker-compose.yml`, `.env.example`)
3) **Gateway returns 502** → ensure upstream services are healthy (`docker compose ps`). (`gateway/nginx.conf`)
4) **Celery workers unhealthy** → confirm Redis is healthy and `CELERY_BROKER_URL`. (`docker-compose.yml`)
5) **Metrics missing** → confirm `/metrics` endpoints and Prometheus targets. (`infra/prometheus.yml`)

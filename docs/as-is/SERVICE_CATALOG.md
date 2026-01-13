# NEFT Platform — Service Catalog (AS-IS)

> **Source of truth:** `docker-compose.yml`, service entrypoints in `platform/*`, `services/*`, `gateway/`, and infra configs.
> 
> **Scope:** only services defined in compose are listed. If something exists in code but is not present in compose, it is marked **NOT IMPLEMENTED (compose)**.

## Legend
- **Ports**: host:container. If `expose` only, the service is internal to the docker network.
- **Health/metrics** paths are literal paths from service code/config.
- **Deps** are taken from `depends_on` in `docker-compose.yml`.

## Core runtime services

| Service | Container | Build/Image | Ports | Health | Metrics | Deps | Notes |
|---|---|---|---|---|---|---|---|
| gateway | `neft-processing-gateway-1` | `gateway/Dockerfile` | `80:80` | `GET /health` | `GET /metrics` | core-api, auth-host, ai-service | Routes `/api/core`, `/api/auth`, `/api/ai`, `/api/logistics`, `/api/docs`, `/api/int`, `/api/integrations`, `/admin/`, `/client/`, `/partner/`. (`gateway/nginx.conf`) |
| core-api | `neft-processing-core-api-1` | `platform/processing-core/Dockerfile` | `8001:8000` | `GET /api/core/health` | `GET /metrics` | postgres, redis, minio-init | Main FastAPI API. (`platform/processing-core/app/main.py`) |
| auth-host | `neft-processing-auth-host-1` | `platform/auth-host/Dockerfile` | `8002:8000` | `GET /api/auth/health` | `GET /api/v1/metrics` | postgres, redis | JWT/identity/bootstrap. Demo users seeded via `DEMO_SEED_ENABLED=1` + `python -m app.cli.reset_passwords --demo --force`. (`platform/auth-host/app/main.py`) |
| ai-service | `neft-processing-ai-service-1` | `platform/ai-services/risk-scorer/Dockerfile` | `8003:8000` | `GET /api/v1/health` | `GET /metrics` | redis | Risk scoring stub. (`platform/ai-services/risk-scorer/app/main.py`) |
| integration-hub | `neft-processing-integration-hub-1` | `platform/integration-hub/Dockerfile` | `8010:8000` | `GET /health` | `GET /metrics` | postgres, redis, minio-init, gateway | Webhooks + EDO stub. (`platform/integration-hub/neft_integration_hub/main.py`) |
| workers | `neft-processing-workers-1` | `platform/billing-clearing/Dockerfile` | internal only | Celery ping (healthcheck in compose) | n/a | core-api, redis, minio-init | Celery workers for billing/pdf/clearing. (`platform/billing-clearing`) |
| beat | `neft-processing-beat-1` | `platform/billing-clearing/Dockerfile` | internal only | Celery connection check | n/a | core-api, redis, minio-init | Celery beat scheduler. |
| flower | `neft-processing-flower-1` | `services/flower/Dockerfile` | `5555:5555` | Flower API check | Flower UI (same port) | redis, workers | Monitoring UI for Celery. |
| celery-exporter | `celery-exporter` | `danihodovic/celery-exporter:latest` | internal only (`9808`) | `GET /metrics` | `GET /metrics` | redis | Prometheus exporter for Celery. |

## Frontends

| Service | Container | Build/Image | Ports | Health | Metrics | Deps | Notes |
|---|---|---|---|---|---|---|---|
| admin-web | `neft-processing-admin-web-1` | `frontends/admin-ui/Dockerfile` | `4173:80` | `GET /health` | n/a | none | Served via gateway `/admin/`. (`gateway/nginx.conf`) |
| client-web | `neft-processing-client-web-1` | `frontends/client-portal/Dockerfile` | `4174:80` | `GET /health` | n/a | none | Served via gateway `/client/`. (`gateway/nginx.conf`) |
| partner-web | `neft-processing-partner-web-1` | `frontends/partner-portal/Dockerfile` | `4175:80` | `GET /health` | n/a | gateway | Served via gateway `/partner/`. (`gateway/nginx.conf`) |

## Peripheral API services

| Service | Container | Build/Image | Ports | Health | Metrics | Deps | Notes |
|---|---|---|---|---|---|---|---|
| crm-service | `neft-processing-crm-1` | `platform/crm-service/Dockerfile` | internal only (`8000`) | `GET /health` | `GET /metrics` | none | Stub service. (`platform/crm-service/app/main.py`) |
| logistics-service | `neft-processing-logistics-1` | `platform/logistics-service/Dockerfile` | internal only (`8000`) | `GET /health` | `GET /metrics` | none | Mock logistics provider by default. (`platform/logistics-service/neft_logistics_service/main.py`) |
| document-service | `neft-processing-document-1` | `platform/document-service/Dockerfile` | internal only (`8000`) | `GET /health` | `GET /metrics` | none | PDF render/sign/verify. (`platform/document-service/app/main.py`) |

## Data + infra services

| Service | Container | Build/Image | Ports | Health | Metrics | Deps | Notes |
|---|---|---|---|---|---|---|---|
| postgres | `neft-processing-postgres-1` | `postgres:16` | `5432:5432` | `pg_isready` | n/a | none | Primary DB for core/auth/integration-hub (if `DATABASE_URL` uses Postgres). |
| redis | `neft-processing-redis-1` | `redis:7.4-alpine` | `6379:6379` | `redis-cli ping` | n/a | none | Cache + Celery broker/result backend. |
| clickhouse | `neft-processing-clickhouse-1` | `clickhouse/clickhouse-server:24.6` | `8123:8123`, `9002:9000` | n/a | n/a | none | Optional BI storage. (`shared/python/neft_shared/settings.py`) |
| minio | `neft-processing-minio-1` | `quay.io/minio/minio` | `9000:9000`, `9001:9001` | `GET /minio/health/ready` | n/a | none | S3-compatible storage. (`infra/minio-init.sh`) |
| minio-health | `neft-processing-minio-health-1` | `curlimages/curl:8.12.1` | n/a | `GET /minio/health/ready` | n/a | minio | Health gate for minio-init. |
| minio-init | `neft-processing-minio-init-1` | `quay.io/minio/mc` | n/a | n/a | n/a | minio-health | Initializes buckets. (`infra/minio-init.sh`) |
| otel-collector | `neft-processing-otel-collector-1` | `infra/otel-collector.Dockerfile` | `4317:4317` | `GET /` on 13133 | n/a | none | Receives OTLP. (`infra/otel-collector-config.yaml`) |
| jaeger | `neft-processing-jaeger-1` | `jaegertracing/all-in-one:1.55` | `16686:16686`, `14250:14250` | `GET /` on 16686 | n/a | otel-collector | Traces UI. |
| prometheus | `neft-processing-prometheus-1` | `prom/prometheus:v2.52.0` | `9090:9090` | `GET /-/healthy` | `GET /metrics` | gateway | Scrapes metrics. (`infra/prometheus.yml`) |
| grafana | `neft-processing-grafana-1` | `grafana/grafana:10.4.1` | `3000:3000` | `GET /health` | n/a | prometheus | Dashboards in `infra/grafana/`. |
| loki | `neft-processing-loki-1` | `grafana/loki:2.9.10` | `3100:3100` | n/a | n/a | none | Log aggregation backend. (`infra/loki/loki-config.yml`) |
| promtail | `neft-processing-promtail-1` | `grafana/promtail:2.9.10` | `9080:9080` | n/a | n/a | loki | Log shipper. (`infra/promtail/promtail-config.yml`) |

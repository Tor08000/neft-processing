# Bootstrap and smoke check (Windows CMD)

## Start the stack

```cmd
docker compose up -d
```

Wait for the core API to become healthy:

```cmd
docker compose ps
```

## Ports and URLs

| Service | URL | Notes |
| --- | --- | --- |
| Core API | http://localhost:8001/api/core/health | Health check |
| Core API metrics | http://localhost:8001/metrics | Prometheus scrape |
| Gateway | http://localhost/ | HTTP 80 |
| Gateway → Core | http://localhost/api/core/health | Through gateway |
| Auth host | http://localhost:8002/api/auth/health | Auth API |
| Flower | http://localhost:5555/ | May return 401 if basic auth enabled |
| Grafana | http://localhost:3000/ | Dashboards |
| Prometheus | http://localhost:9090/-/ready | Ready endpoint |
| Jaeger | http://localhost:16686/ | UI |
| MinIO | http://localhost:9000/minio/health/ready | Health endpoint |
| Postgres | localhost:5432 | Use docker exec/psql |

## Run the smoke script

```cmd
scripts\smoke_all.cmd
```

This script checks:

- Core API health + metrics
- Gateway routing
- Auth host health
- Flower availability
- Grafana/Prometheus/Jaeger availability
- MinIO readiness
- Postgres connectivity
- Alembic heads/current/version table state
- Prometheus core-api target status

## Full verification guard

```cmd
scripts\verify_all.cmd
```

This script:

- Brings the stack up
- Waits for core-api health
- Runs Alembic heads/current checks
- Verifies `processing_core.alembic_version_core` contains current heads
- Runs `scripts\smoke_all.cmd`

## Logs

Check container logs (last 200 lines):

```cmd
docker logs --tail 200 neft-processing-core-api-1
docker logs --tail 200 neft-processing-gateway-1
docker logs --tail 200 neft-processing-auth-host-1
docker logs --tail 200 neft-processing-postgres-1
```

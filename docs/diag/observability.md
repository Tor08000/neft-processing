# Observability quickstart

## Logs
- Gateway emits JSON access logs with upstream latency; inspect `services/gateway/nginx.conf` for the `json_logs` format.
- Application services rely on `neft_shared.logging_setup` and inherit `SERVICE_NAME` for consistent tagging.

## Traces
- Default OTLP target: `http://otel-collector:4317` (see `docker-compose.yml`).
- Enable by setting `NEFT_ENV` to `dev` or `staging`; `local` keeps tracing disabled by default via config scaffolding.
- Jaeger UI available at `http://localhost:16686` when docker compose stack is running.

## Metrics
- Prometheus is provisioned via `infra/prometheus.yml` and scrapes service `/metrics` endpoints where available.
- Grafana dashboards are mounted from `infra/grafana/dashboards` and auto-provisioned into the `Neft` folder.
- Default credentials: `admin` / `admin`.

## Safety checks
- Run `python scripts/check_migrations.py` before deploys to verify alembic head matches the database.
- Use `python scripts/print_alembic_state.py` to inspect head/current revisions.
- Generate a SQL-only snapshot with `python scripts/dump_schema.py` when auditing schema drift.

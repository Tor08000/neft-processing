# Runbook: Fleet ingestion lag

## Symptoms
- Увеличился lag ingestion.
- Нет новых транзакций/событий от провайдера.
- Очередь ingestion растет.

## Impact
- Отставание данных по флоту/провайдерам.
- Некорректные или неполные отчеты.

## Primary dashboards/queries
- Grafana dashboard: **Logs Overview** (Loki) — фильтр `service=core-api`/`workers`.
- Grafana dashboard: **Core Incident Logs** — панель “Ingestion errors”.
- Prometheus queries:
  - `fleet_ingestion_lag_seconds`
  - `ingestion_jobs_pending`
  - `celery_queue_length{queue="ingestion"}`
- Loki queries:
  - `{service=~"core-api|workers"} |= "fleet_ingestion" |= "error"`
  - `{service=~"core-api|workers"} |= "provider" |= "timeout"`

## Immediate actions (первые 5 минут)
1. Проверить доступность провайдера (virtual/stub).
2. Проверить рост lag/очередей.
3. Просмотреть ошибки ingestion в Loki.

## Diagnosis steps
1. Проверить latency Redis/Postgres.
2. Убедиться, что ingestion воркеры живы.
3. Проверить dedupe-конфликты или повторные события.
4. Оценить необходимость replay/backfill.

## Mitigation
- Перезапустить ingestion workers.
- Запустить replay/backfill job.
- Временно ограничить входящие запросы от провайдера (если есть возможность).
- Устранить конфликт dedupe ключей.

## Verification
- `fleet_ingestion_lag_seconds` стабилизируется и падает.
- Очередь ingestion уменьшается.
- Ошибки в Loki больше не растут.

## Postmortem checklist
- Сохранить графики метрик lag/queue.
- Зафиксировать логи провайдера и timeout события.
- Описать первопричину и корректирующие действия.

## Windows CMD commands
```
curl -fsS http://localhost:8001/api/core/health
curl -fsS http://localhost:5555/api/workers?refresh=1

curl -fsS http://localhost:9090/api/v1/query?query=fleet_ingestion_lag_seconds

docker compose ps

docker compose logs workers --since 30m

docker compose restart workers
```

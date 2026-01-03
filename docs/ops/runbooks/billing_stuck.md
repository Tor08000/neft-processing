# Runbook: Billing stuck

## Symptoms
- Платежные документы не появляются или появляются с задержкой.
- Очередь billing задач растет и не снижается.
- Ошибки billing в логах core-api/workers.

## Impact
- Задержка биллинга и выставления счетов.
- Нарушение SLA по расчетам.

## Primary dashboards/queries
- Grafana dashboard: **Logs Overview** (Loki) — фильтр `service=core-api` или `service=workers`.
- Grafana dashboard: **Core Incident Logs** — панель “Billing errors”.
- Prometheus queries:
  - `billing_job_last_run_timestamp`
  - `celery_queue_length{queue="billing"}`
  - `celery_tasks_failed_total{queue="billing"}`
- Loki queries:
  - `{service="core-api"} |= "billing" |= "error"`
  - `{service="workers"} |= "billing"`

## Immediate actions (первые 5 минут)
1. Проверить health core-api и workers.
2. Проверить, что `beat` запущен и публикует расписание.
3. Проверить рост очереди billing.
4. Найти последние ошибки billing в Loki.

## Diagnosis steps
1. Убедиться, что есть свежий `billing_job_last_run_timestamp`.
2. Проверить состояние Celery worker/beat и backlog по очереди `billing`.
3. Посмотреть ошибки в Loki по `billing` и `error`.
4. Проверить наличие задач в deadletter/outbox (если используется).

## Mitigation
- Перезапустить `workers` и `beat`.
- Повторно запустить billing job вручную (если есть endpoint).
- Очистить зависшие задачи и переинициализировать очередь billing.

## Verification
- `billing_job_last_run_timestamp` обновляется.
- Очередь `billing` уменьшается.
- Ошибки billing исчезают из Loki.

## Postmortem checklist
- Сохранить графики метрик и примеры логов.
- Зафиксировать время начала/окончания инцидента.
- Описать первопричину (beat не запущен, зависшая задача, deadletter/outbox).
- Зафиксировать ручные действия и их эффект.

## Windows CMD commands
```
curl -fsS http://localhost:8001/api/core/health
curl -fsS http://localhost:5555/api/workers?refresh=1
curl -fsS http://localhost:5555/api/queues/length

docker compose ps

docker compose logs workers --since 15m

docker compose restart workers

docker compose restart beat
```

# Scheduler / Celery Beat диагностика

## Запуск beat

Beat запускается через единый entrypoint контейнера:

```bash
ROLE=beat python -m celery -A services.workers.app.celery_app:celery_app beat --loglevel=INFO
```

Важно: при импорте `services.workers.app.celery_app` расписание загружается из
`platform/billing-clearing/app/beat.py`, поэтому beat невозможно поднять без расписания.

## Как проверить, что расписание загружено

1. Логи beat должны содержать строку:

```
[beat] schedule loaded: <N> tasks
```

2. Проверка API:

```bash
curl -s http://core-api:8000/api/v1/health/scheduler | jq
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "beat": {
    "alive": true,
    "last_heartbeat_at": "2025-01-01T12:00:00+00:00",
    "schedule_loaded_at": "2025-01-01T12:00:00+00:00"
  },
  "schedule": {
    "loaded": true,
    "task_count": 5
  },
  "jobs": {
    "billing": { "last_run_at": "2025-01-01T01:00:00+00:00" },
    "clearing": { "last_run_at": "2025-01-01T02:00:00+00:00" },
    "billing_finalize": { "last_run_at": "2025-01-01T13:00:00+00:00" }
  }
}
```

## Как проверить выполнение задач

Каждый запуск периодической задачи пишет запись в таблицу `scheduler_job_runs`:

```sql
SELECT job_name, status, started_at, finished_at, celery_task_id
FROM scheduler_job_runs
ORDER BY started_at DESC
LIMIT 20;
```

Также в логах воркеров появляются строки:

```
[job] started: <job_name> celery_task_id=...
[job] finished: <job_name> status=SUCCESS duration_ms=...
[job] failed: <job_name> error=...
```

## Типовые ошибки

### Beat жив, задач нет

Симптомы:
- `/api/v1/health/scheduler` возвращает `schedule.loaded: false` или `task_count: 0`.
- В логах beat нет строки `[beat] schedule loaded`.

Действия:
- Проверьте, что beat запускается через `services.workers.app.celery_app`.
- Убедитесь, что переменная `ROLE=beat` или `CELERY_BEAT=true` установлена.
- Проверьте, что `platform/billing-clearing/app/beat.py` импортируется без ошибок.

### Beat жив, но jobs не выполняются

Симптомы:
- `beat.alive: true`, но `jobs.*.last_run_at` пустые.
- В логах нет `[job] started` для нужных задач.

Действия:
- Проверьте, что воркеры подняты и подключены к брокеру.
- Убедитесь, что очередь и routing совпадают с настройками `CELERY_DEFAULT_QUEUE`.
*** End Patch"}}

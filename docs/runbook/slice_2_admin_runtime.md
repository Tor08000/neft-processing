# Slice 2: Admin Runtime Center

## Цель
За 60 секунд ответить на вопросы: «Платформа жива? где пожар? что блокирует деньги?» без write-операций.

## Endpoint
`GET /api/core/v1/admin/runtime/summary`

Legacy alias: `GET /api/core/admin/runtime/summary` → `308` redirect to canonical v1 endpoint.

## Пример ответа
```json
{
  "ts": "2026-01-24T15:00:00Z",
  "environment": "prod",
  "read_only": false,
  "health": {
    "core_api": "UP",
    "auth_host": "UP",
    "gateway": "UP",
    "postgres": "UP",
    "redis": "UP",
    "minio": "UP",
    "clickhouse": "UP"
  },
  "queues": {
    "settlement": { "depth": 0, "oldest_age_sec": 0 },
    "payout": { "depth": 0, "oldest_age_sec": 0 },
    "blocked_payouts": { "count": 0 },
    "payment_intakes_pending": { "count": 0 }
  },
  "violations": {
    "immutable": { "count": 0, "top": [] },
    "invariants": { "count": 0, "top": [] }
  },
  "money_risk": {
    "payouts_blocked": 0,
    "settlements_pending": 0,
    "overdue_clients": 0
  },
  "events": {
    "critical_last_10": []
  }
}
```

## Как интерпретировать статусы
- **UP** — сервис отвечает и не сигнализирует деградацию.
- **DEGRADED** — сервис частично доступен или отвечает с задержками; требуется проверка.
- **DOWN** — сервис недоступен, требуется немедленная реакция.

## Smoke (Windows CMD)
```cmd
scripts\smoke_slice_2_admin_runtime.cmd
```
Скрипт логинит admin, проверяет `/api/core/v1/admin/runtime/summary`, печатает env/read_only и ключевые статусы.

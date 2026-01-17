# Client Portal v1.6 — Deep Integration & Control

## Цель v1.6

Переход от режима «платформа показывает» к режиму «платформа управляет процессами».

Ключевые изменения:
- helpdesk становится двусторонним;
- аналитика — расследуемой, а не обзорной;
- экспорт — предсказуемым (ETA);
- каждый пользователь видит свой дашборд;
- SLA/SLO — формализованы и измеримы.

## EPIC 1 — Inbound Helpdesk Webhooks (P0)

### 1.1 Цель

Синхронизировать изменения из helpdesk → в NEFT:
- комментарии оператора;
- смена статуса;
- (опционально) приоритет.

### 1.2 Webhook endpoint

`POST /api/core/webhooks/helpdesk/{provider}`

Требования:
- без аутентификации по cookie;
- только HMAC signature (shared secret);
- timestamp + replay protection.

### 1.3 Inbound события (v1.6)

- `comment_created`
- `ticket_status_changed`
- `ticket_priority_changed` (P1)

### 1.4 Маппинг

По `external_ticket_id`:
- найти `internal_ticket_id`;
- добавить комментарий в NEFT;
- изменить статус (OPEN / IN_PROGRESS / CLOSED).

### 1.5 Safety

- inbound события не триггерят outbound (защита от loop);
- webhook errors логируются, но не ломают систему;
- rate limit на endpoint.

## EPIC 2 — BI Drill-down (P0)

### 2.1 Цель

Дать возможность проваливаться из агрегатов в детали.

### 2.2 Drill-down маршруты

Из `/client/analytics`:
- клик по дню → `/client/analytics/day?date=YYYY-MM-DD`;
- клик по card → `/client/cards/:id?from=&to=`;
- клик по driver → `/client/users/:id?from=&to=`;
- клик по SLA breach → `/client/support?filter=sla_breached`.

### 2.3 Backend

Добавить:
- `/api/core/client/analytics/day`
- `/api/core/client/analytics/card/:id`
- `/api/core/client/analytics/driver/:id`

Общие требования:
- org-scoped;
- period required;
- pagination обязательна.

## EPIC 3 — Export ETA / Progress Streaming (P0)

### 3.1 Цель

Пользователь видит не только %, но и ожидаемое время завершения.

### 3.2 ETA модель

Расширить `ExportJob`:
- `started_at`
- `processed_rows`
- `estimated_total_rows`
- `avg_rows_per_sec` (скользящее среднее)
- `eta_seconds` (computed, не хранить)

### 3.3 Расчёт ETA

```
remaining = estimated_total_rows - processed_rows
eta = remaining / avg_rows_per_sec
```

- avg обновлять каждые N секунд;
- если total неизвестен → ETA не показывать.

### 3.4 Streaming прогресс (P1)

Варианты:
- long-polling `/exports/jobs/:id/stream`
- SSE (Server-Sent Events)

Для v1.6 достаточно polling + ETA, streaming оставить как P1.

## EPIC 4 — User Dashboards (P0)

### 4.1 Цель

Каждый пользователь видит релевантный дашборд, а не общий.

### 4.2 Типы дашбордов

- OWNER / ADMIN: бизнес + операции + SLA
- ACCOUNTANT: финансы + документы
- FLEET_MANAGER: карты + расход + аномалии
- DRIVER (v1.6 можно read-only): свои операции + карты

### 4.3 Реализация

`/client/dashboard` рендерится из `dashboard_config`.

Backend отдаёт:

```json
{
  "widgets": [
    {"type": "kpi", "key": "total_spend"},
    {"type": "chart", "key": "spend_timeseries"},
    {"type": "list", "key": "top_cards"}
  ]
}
```

UI просто рендерит конфиг.

## EPIC 5 — SLO / SLA Framework (P0)

### 5.1 Цель

Переход от «SLA как таймер» к формализованному контролю качества.

### 5.2 SLO объекты

Примеры:
- Export SLO: 95% exports < 10 минут
- Email SLO: 99% emails delivered < 60 секунд
- Support SLO: first response < 2 часа

### 5.3 Модель

`service_slo`:
- service (export/email/support)
- metric
- objective (p95 < X)
- window (7d/30d)

### 5.4 Breach detection

Периодический evaluator:
- breach → audit + notification + BI.

## Observability расширение (P1)

- SLO burn-rate
- error budget remaining
- SLO breaches on dashboard

## Что НЕ делаем в v1.6

- auto-remediation
- ML/AI прогнозы
- user-defined SLO
- cross-org BI

## Порядок реализации v1.6

1. Inbound Helpdesk Webhooks
2. BI Drill-down
3. Export ETA
4. User Dashboards
5. SLO / SLA Framework

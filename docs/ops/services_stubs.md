# Service stubs (crm/logistics/document)

## Зачем это нужно

Сервисы `crm-service`, `logistics-service`, `document-service` — это технические заглушки.
Они существуют, чтобы:

- контейнеры были "живыми" и наблюдаемыми (health/metrics),
- обеспечить понятные контракты интеграции,
- безопасно заменить/развивать их позже без "архитектурной лжи".

Текущая версия заглушек: `stub-v0`.

## Где сейчас доменная логика

Бизнес-логика этих доменов остаётся в `core-api` до переноса в отдельные сервисы.
В заглушках нет БД, миграций, очередей и прочей инфраструктуры.

## Проверка доступности

Напрямую:

- `http://crm-service:8000/health`
- `http://logistics-service:8000/health`
- `http://document-service:8000/health`

Ответ:

```json
{"status": "ok", "service": "...", "version": "stub-v0"}
```

Метрики Prometheus:

- `http://crm-service:8000/metrics`
- `http://logistics-service:8000/metrics`
- `http://document-service:8000/metrics`

Примеры метрик:

```
crm_service_up 1
crm_service_http_requests_total{method="GET",path="/health",status="200"} 1
```

## Проверка через gateway

Минимальные маршруты доступны через gateway:

- `/api/crm/` → `crm-service:8000`
- `/api/logistics/` → `logistics-service:8000`
- `/api/docs/` → `document-service:8000`

Например:

- `http://gateway/api/crm/health`
- `http://gateway/api/logistics/health`
- `http://gateway/api/docs/health`

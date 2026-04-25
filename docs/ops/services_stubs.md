# Service compatibility surfaces (crm/logistics/document)

## Зачем это нужно

Исторически `crm-service`, `logistics-service`, `document-service` шли как отдельный "stub" набор.
Текущий repo-truth уже другой:

- `crm-service` — compatibility/shadow CRM surface, не canonical CRM owner
- `logistics-service` — реальный logistics compute/preview service с explicit provider modes
- `document-service` — реальный internal render/sign/verify service с explicit provider modes

Общее у них только одно: это отдельные внутренние сервисы с health/metrics и gateway routing.

## Где сейчас доменная логика

Где сейчас owner truth:

- CRM control plane owner: `processing-core` admin CRM (`/api/core/v1/admin/crm/*`)
- CRM compatibility/shadow routes: `crm-service` (`/api/v1/crm/*`, `/api/crm/*`)
- Logistics compute owner: `logistics-service`
- Logistics snapshot/evidence owner: `processing-core`
- Documents orchestration owner: `processing-core`
- Signing/render engine owner: `document-service`

## Проверка доступности

Напрямую:

- `http://crm-service:8000/health`
- `http://logistics-service:8000/health`
- `http://document-service:8000/health`

Ответ health:

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

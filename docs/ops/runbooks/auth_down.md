# Runbook: Auth down

## Symptoms
- Ошибки авторизации, токены не выдаются.
- Grafana alert: Auth latency spike / Auth down.

## Impact
- Вход и любые операции с авторизацией невозможны.

## Immediate actions
1. Проверить статус auth сервиса.
2. Проверить connectivity к базе и кешу.
3. Перезапустить сервис.

## Verification
- Успешный login/refresh.
- p95 latency в пределах SLO.

## Rollback
- Откат до последнего стабильного образа.

## Escalation
- Primary → Secondary при простое > 10 минут.

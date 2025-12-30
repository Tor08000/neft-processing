# Runbook: Core API down

## Symptoms
- 5xx на /health и core endpoints.
- Grafana alert: Core API down.

## Impact
- Клиентские и админские операции недоступны.

## Immediate actions
1. Проверить статус деплоя/подов.
2. Проверить подключение к Postgres/Redis.
3. Перезапуск сервиса при необходимости.

## Verification
- /health возвращает 200.
- p95 latency в пределах SLO.

## Rollback
- Откат на последнюю стабильную версию.

## Escalation
- Primary → Secondary при отсутствии восстановления за 15 минут.

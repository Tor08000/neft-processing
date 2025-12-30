# Runbook: E-sign provider down

## Symptoms
- Ошибки вызовов e-sign API.
- Рост статусов FAILED на подписи.

## Impact
- Подписи не создаются/не подтверждаются.

## Immediate actions
1. Проверить статус провайдера.
2. Включить retry/backoff, если отключено.
3. Ограничить новые подписи при массовом сбое.

## Verification
- Новые подписи проходят.
- FAILED не растет.

## Rollback
- Откат конфигурации интеграции.

## Escalation
- Primary → Secondary, уведомить бизнес.

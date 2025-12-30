# Runbook: EDO provider down

## Symptoms
- Ошибки отправки/получения ЭДО.
- Рост retries в интеграции.

## Impact
- Обмен документами задерживается.

## Immediate actions
1. Проверить статус провайдера ЭДО.
2. Убедиться, что ретраи включены.
3. Увеличить retry интервал при rate limit.

## Verification
- Очередь ЭДО уменьшается.
- Новые документы доставляются.

## Rollback
- Откат конфигурации интеграции.

## Escalation
- Primary → Secondary, уведомить бизнес.

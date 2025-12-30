# Runbook: Billing/Clearing stuck

## Symptoms
- Billing/Clearing jobs не завершаются в SLA.
- Рост очереди задач.

## Impact
- Задержка выставления счетов и клиринга.

## Immediate actions
1. Проверить состояние job workers.
2. Проверить зависимости (DB, Redis, integration-hub).
3. Перезапустить worker и повторить задачи.

## Verification
- Новые jobs завершаются в SLA.
- Очередь уменьшается.

## Rollback
- Откат последнего изменения в job pipeline.

## Escalation
- Primary → Secondary при задержке > 1 SLA window.

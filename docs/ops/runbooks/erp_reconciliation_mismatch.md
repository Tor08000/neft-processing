# Runbook: ERP reconciliation mismatch

## Symptoms
- Статусы reconciliation в FAILED.
- Несоответствие сумм между NEFT и ERP.

## Impact
- Финансовые расхождения, риск потери денег.

## Immediate actions
1. Остановить автоматическую синхронизацию (если нужно).
2. Снять сверку по последнему периоду.
3. Перезапустить reconciliation job после проверки данных.

## Verification
- Статусы reconciliation переходят в SUCCESS.
- Суммы совпадают.

## Rollback
- Откат последнего изменения в интеграции.

## Escalation
- Primary → Secondary → Business.

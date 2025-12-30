# Runbook: High error rate / latency spike

## Symptoms
- p95/p99 растут выше SLO.
- Error rate > 0.1%.

## Impact
- Деградация пользовательских операций.

## Immediate actions
1. Проверить метрики нагрузки (CPU/RAM/DB connections).
2. Проверить внешние зависимости (Redis, MinIO, document-service).
3. Включить rate limiting при необходимости.

## Verification
- Метрики возвращаются в SLO.
- Error rate снижается.

## Rollback
- Откат последнего релиза.

## Escalation
- Primary → Secondary при устойчивой деградации > 15 минут.

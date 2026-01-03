# Runbook: Audit verification failed

## Symptoms
- Verify endpoint возвращает fail.
- Export verification not ok.
- Ошибки audit verify в логах.

## Impact
- Нарушение целостности аудита.
- Невозможность подтвердить цепочку подписи.

## Primary dashboards/queries
- Grafana dashboard: **Logs Overview** (Loki) — фильтр `service=core-api`.
- Grafana dashboard: **Core Incident Logs** — панель “Audit verification errors”.
- Loki queries:
  - `{service="core-api"} |= "audit" |= "verify" |= "failed"`

## Immediate actions (первые 5 минут)
1. Проверить режим подписи (local/kms/vault).
2. Проверить наличие key registry записи.
3. Проверить доступность хранилища (S3/object lock).

## Diagnosis steps
1. Проверить continuity цепочки `prev_hash`.
2. Проверить актуальность ключей и их доступность.
3. Проверить сетевую доступность S3 и права доступа.

## Mitigation
- Временно переключить signer в local (если допустимо в local env).
- Перезапустить сервис подписи/верификации.
- Прогнать trust verification scripts.

## Verification
- Verify endpoint возвращает success.
- Ошибки audit verify перестают появляться в Loki.

## Postmortem checklist
- Сохранить логи verify и результаты проверки цепочки.
- Зафиксировать режим подписи и состояние key registry.
- Описать первопричину и корректирующие действия.

## Windows CMD commands
```
curl -fsS http://localhost:8001/api/core/health
curl -fsS http://localhost:8001/api/core/audit/verify

docker compose logs core-api --since 30m

docker compose restart core-api
```

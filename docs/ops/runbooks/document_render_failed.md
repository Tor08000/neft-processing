# Runbook: Document render failed

## Symptoms
- Ошибки при генерации документов.
- Увеличение статусов FAILED в документах.

## Impact
- Невозможность финализации документов.

## Immediate actions
1. Проверить document-service.
2. Проверить доступ к MinIO.
3. Перезапустить document-service.

## Verification
- Документ успешно рендерится и сохраняется.
- Ошибки не растут.

## Rollback
- Откат document-service.

## Escalation
- Primary → Secondary при массовых сбоях.

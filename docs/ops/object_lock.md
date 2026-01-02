# Object Lock для экспортов (S3/MinIO)

## Создание bucket с Object Lock

### AWS S3
1. Создайте bucket с включённым Object Lock:
   ```bash
   aws s3api create-bucket --bucket neft-exports --object-lock-enabled-for-bucket
   ```
2. Включите версионирование:
   ```bash
   aws s3api put-bucket-versioning --bucket neft-exports --versioning-configuration Status=Enabled
   ```

### MinIO
1. Создайте bucket с Object Lock и версионированием:
   ```bash
   mc mb --with-lock local/neft-exports
   mc version enable local/neft-exports
   ```

## Включение governance-режима

Включите настройки:
```
S3_OBJECT_LOCK_ENABLED=true
S3_OBJECT_LOCK_MODE=GOVERNANCE
S3_OBJECT_LOCK_RETENTION_DAYS=180
S3_OBJECT_LOCK_LEGAL_HOLD=false
```

Если `S3_OBJECT_LOCK_RETENTION_DAYS` не задан, используется `AUDIT_EXPORT_RETENTION_DAYS`.

## Проверка retention

```bash
aws s3api head-object --bucket neft-exports --key exports/<path>
```
В ответе должны быть поля:
- `ObjectLockMode`
- `ObjectLockRetainUntilDate`

## Поведение purge

- Purge удаляет только экспорты, у которых истёк `retention_until`.
- При включённом Object Lock дополнительно проверяется `locked_until`.
- Если удаление возвращает `AccessDenied`, экспорт помечается как ещё заблокированный, а успешный purge-лог не пишется.

# Backups v1

## Postgres
- Ежедневный full backup.
- WAL / incremental: включить при наличии инфраструктурной поддержки.
- Хранение: ≥ 7–14 дней.

### Где лежат бэкапы
- Хранилище: TBD (S3/MinIO bucket, путь).
- Доступ: через backup service account.

### Проверка целостности
- Регулярно выполнять restore в тестовую БД.
- Проверки:
  - `alembic current`
  - `select 1`

## MinIO / S3
- Versioning: включено (уже есть).
- Lifecycle policy: включить на документы.
- Резервная копия: cross-region replication либо регулярный backup бакета документов.

## Job: backup_verify
- Назначение: автоматическая проверка восстановления.
- Шаги:
  1. Restore последнего backup в тестовую БД.
  2. Smoke-проверка (`alembic current`, `select 1`).
  3. Отчет в audit/logs.
- Частота: ежедневно/еженедельно (TBD).

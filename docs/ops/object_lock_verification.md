# Object lock verification (MinIO/S3)

## Purpose / Что проверяем
Проверяем, что при включённом `S3_OBJECT_LOCK_ENABLED` экспортные артефакты пишутся в S3/MinIO с retention/legal hold, а удаление/перезапись блокируется до истечения срока. Контрольные поля в БД: `case_exports.object_key`, `case_exports.locked_until`, `case_exports.retention_until`.

## Prerequisites / Что нужно
- Запущенный стенд: `docker compose up -d`.
- Доступ к gateway: `http://localhost`.
- Установлены `curl`, `docker`, `psql` (через `docker compose exec`).
- Для MinIO — доступ к `mc` (через `docker compose run --rm --entrypoint mc minio-init`).

## Step-by-step / Пошагово
1. Включите Object Lock в `.env` и задайте отдельный bucket (object lock включается только при создании bucket):
   ```env
   S3_OBJECT_LOCK_ENABLED=true
   S3_OBJECT_LOCK_MODE=GOVERNANCE
   S3_OBJECT_LOCK_RETENTION_DAYS=7
   S3_OBJECT_LOCK_LEGAL_HOLD=false
   S3_BUCKET_EXPORTS=case-exports-lock
   ```
   Перезапустите core-api:
   ```cmd
   docker compose up -d --build core-api
   ```

2. Создайте bucket с Object Lock (MinIO локально):
   ```cmd
   docker compose run --rm --entrypoint mc minio-init alias set local http://minio:9000 change-me change-me
   docker compose run --rm --entrypoint mc minio-init mb --with-lock local/case-exports-lock
   docker compose run --rm --entrypoint mc minio-init version enable local/case-exports-lock
   ```
   (Если bucket уже существует без lock, удалите его в dev-стенде и пересоздайте.)

3. Получите admin-токен:
   ```cmd
   curl -X POST http://localhost/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
   ```

4. Создайте тестовый кейс и экспорт (создаёт S3-объект):
   ```cmd
   curl -X POST http://localhost/api/core/cases -H "Authorization: Bearer <ACCESS_TOKEN>" -H "Content-Type: application/json" -d "{\"kind\":\"operation\",\"title\":\"Object lock check\"}"
   curl -X POST http://localhost/api/core/v1/admin/exports -H "Authorization: Bearer <ACCESS_TOKEN>" -H "Content-Type: application/json" -d "{\"kind\":\"CASE\",\"case_id\":\"<CASE_ID>\",\"payload\":{\"note\":\"object lock check\"}}"
   ```
   Скопируйте `id` экспорта.

5. Найдите `object_key` и даты retention в БД:
   ```cmd
   docker compose exec -T postgres psql -U neft -d neft -c "SET search_path TO processing_core; SELECT id, object_key, locked_until, retention_until FROM case_exports ORDER BY created_at DESC LIMIT 1;"
   ```

6. Проверьте retention/legal hold через MinIO client:
   ```cmd
   docker compose run --rm --entrypoint mc minio-init retention info local/case-exports-lock/<OBJECT_KEY>
   docker compose run --rm --entrypoint mc minio-init legalhold info local/case-exports-lock/<OBJECT_KEY>
   ```

7. Попытайтесь удалить объект через пользовательские ключи приложения (должно быть запрещено, используйте `NEFT_S3_ACCESS_KEY/NEFT_S3_SECRET_KEY` из `.env`):
   ```cmd
   docker compose run --rm --entrypoint mc minio-init alias set app http://minio:9000 change-me change-me
   docker compose run --rm --entrypoint mc minio-init rm app/case-exports-lock/<OBJECT_KEY>
   ```

## Expected results / Ожидаемые результаты
- В `case_exports` заполнены `locked_until` и `retention_until` (не `NULL`).
- `mc retention info` показывает `Mode: GOVERNANCE` и `Retain Until` в будущем.
- `mc legalhold info` показывает `LegalHold: OFF` (если `S3_OBJECT_LOCK_LEGAL_HOLD=false`).
- Попытка удаления возвращает ошибку вида `AccessDenied` или `ObjectLocked`.

## Troubleshooting / Если не получилось
- **Retention отсутствует** → bucket создан без Object Lock; пересоздайте с `mc mb --with-lock`.
- **`locked_until` = NULL** → не включён `S3_OBJECT_LOCK_ENABLED` или `S3_OBJECT_LOCK_RETENTION_DAYS` = 0.
- **Удаление всё равно проходит** → используете root-ключи с bypass; проверьте alias (используйте `NEFT_S3_ACCESS_KEY/SECRET`).
- **`mc` недоступен** → используйте MinIO Console (`http://localhost:9001`) и проверьте Object Lock в UI.
- **S3 (AWS) не возвращает ObjectLock поля** → bucket без Object Lock или не включено Versioning.

## Evidence checklist / Что приложить аудитору
- `.env` (маскируя секреты) с `S3_OBJECT_LOCK_*` и `S3_BUCKET_EXPORTS`.
- Команды создания экспорта + ответ (export id).
- SQL-вывод `case_exports` (`object_key`, `locked_until`, `retention_until`).
- Вывод `mc retention info`/`mc legalhold info`.
- Ошибка удаления (AccessDenied/ObjectLocked).

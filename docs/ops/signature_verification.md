# Signature verification (Local / AWS KMS / Vault Transit)

## Purpose / Что проверяем
Проверяем подпись audit-артефактов и событий, которые подписываются `AuditSigningService`: подпись в `case_events` (поля `signature`, `signature_alg`, `signing_key_id`) и подпись экспортов (`case_exports.artifact_signature*`) с верификацией через админские endpoints.

## Prerequisites / Что нужно
- Запущенный стенд: `docker compose up -d`.
- Доступ к gateway: `http://localhost`.
- Установлены `curl`, `docker`, `psql` (через `docker compose exec`).
- Для Local signer — заполненный `AUDIT_SIGNING_PRIVATE_KEY_B64` и перезапуск `core-api`.
- Для AWS KMS/Vault Transit — настроенные интеграции (см. шаги ниже).

## Step-by-step / Пошагово
1. (Local signer) Сгенерируйте ключ и добавьте его в `.env`:
   ```cmd
   docker compose exec -T core-api python -c "from cryptography.hazmat.primitives.asymmetric import ed25519; from cryptography.hazmat.primitives import serialization; import base64; key=ed25519.Ed25519PrivateKey.generate(); pem=key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()); pub=key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo); print('AUDIT_SIGNING_PRIVATE_KEY_B64='+base64.b64encode(pem).decode()); print('PUBLIC_KEY_PEM='); print(pub.decode())"
   ```
   В `.env` установите:
   ```env
   AUDIT_SIGNING_MODE=local
   AUDIT_SIGNING_ALG=ed25519
   AUDIT_SIGNING_KEY_ID=local-dev-key-v1
   AUDIT_SIGNING_PRIVATE_KEY_B64=<PASTE_FROM_COMMAND>
   AUDIT_SIGNING_REQUIRED=true
   ```
   Затем перезапустите core-api:
   ```cmd
   docker compose up -d --build core-api
   ```

2. Получите admin-токен:
   ```cmd
   curl -X POST http://localhost/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
   ```

3. Создайте тестовый кейс (генерирует `case_events`):
   ```cmd
   curl -X POST http://localhost/api/core/cases -H "Authorization: Bearer <ACCESS_TOKEN>" -H "Content-Type: application/json" -d "{\"kind\":\"operation\",\"title\":\"Signature check case\"}"
   ```
   Скопируйте `id` кейса.

4. Создайте экспорт (подписывается и создаёт `case_events` + запись в `case_exports`):
   ```cmd
   curl -X POST http://localhost/api/core/v1/admin/exports -H "Authorization: Bearer <ACCESS_TOKEN>" -H "Content-Type: application/json" -d "{\"kind\":\"CASE\",\"case_id\":\"<CASE_ID>\",\"payload\":{\"note\":\"signature check\"}}"
   ```
   Скопируйте `id` экспорта.

5. Проверьте подписи кейса (audit chain + signatures):
   ```cmd
   curl -X POST http://localhost/api/core/v1/admin/cases/<CASE_ID>/events/verify -H "Authorization: Bearer <ACCESS_TOKEN>"
   ```

6. Проверьте подпись артефакта (case_export_verification_service):
   ```cmd
   curl -X POST http://localhost/api/core/v1/admin/exports/<EXPORT_ID>/verify -H "Authorization: Bearer <ACCESS_TOKEN>"
   ```

7. Посмотрите ключи подписи через админ-API:
   ```cmd
   curl http://localhost/api/core/v1/admin/audit/signing/keys -H "Authorization: Bearer <ACCESS_TOKEN>"
   ```

8. (AWS KMS signer — если настроено)
   - Установите:
     ```env
     AUDIT_SIGNING_MODE=aws_kms
     AUDIT_SIGNING_KEY_ID=<KMS_KEY_ID>
     AWS_REGION=<REGION>
     AWS_ACCESS_KEY_ID=<ACCESS_KEY>
     AWS_SECRET_ACCESS_KEY=<SECRET_KEY>
     AWS_KMS_ENDPOINT=<OPTIONAL_CUSTOM_ENDPOINT>
     AWS_KMS_VERIFY_MODE=local
     ```
   - Перезапустите `core-api` и повторите шаги 3–6.

9. (Vault Transit signer — если настроено)
   - Установите:
     ```env
     AUDIT_SIGNING_MODE=vault_transit
     VAULT_ADDR=<VAULT_URL>
     VAULT_TOKEN=<VAULT_TOKEN>
     VAULT_NAMESPACE=<OPTIONAL_NAMESPACE>
     VAULT_TRANSIT_MOUNT=transit
     VAULT_TRANSIT_KEY=<TRANSIT_KEY_NAME>
     VAULT_VERIFY_MODE=vault
     ```
   - Перезапустите `core-api` и повторите шаги 3–6.

## Expected results / Ожидаемые результаты
- В таблице `processing_core.case_events` заполнены поля `signature`, `signature_alg`, `signing_key_id`, `signed_at`.
- Ответ `/api/core/v1/admin/cases/<CASE_ID>/events/verify` содержит:
  ```json
  {"chain":{"status":"verified"},"signatures":{"status":"verified"}}
  ```
- Ответ `/api/core/v1/admin/exports/<EXPORT_ID>/verify` содержит:
  ```json
  {"content_hash_verified":true,"artifact_signature_verified":true,"audit_chain_verified":true}
  ```
- `/api/core/v1/admin/audit/signing/keys` возвращает активный ключ `key_id` (например, `local-dev-key-v1`).

## Troubleshooting / Если не получилось
- **`artifact_signature_verified=false`** → нет private key (`AUDIT_SIGNING_PRIVATE_KEY_B64`) или неверный `AUDIT_SIGNING_ALG`.
- **`signatures.status=broken`** → у событий отсутствует подпись или ключ не совпадает; проверьте `AUDIT_SIGNING_KEY_ID` и перезапуск core-api.
- **`403 Forbidden`** → нет admin-токена или ролей; проверьте `/api/auth/login` и `NEFT_BOOTSTRAP_ADMIN_ROLES`.
- **`verify` возвращает 404** → кейс/экспорт не создан или удалён.
- **KMS/Vault не подписывает** → проверьте переменные окружения (AWS/Vault), доступность endpoint и права ключа.

## Evidence checklist / Что приложить аудитору
- `.env` (скрывая секреты) с `AUDIT_SIGNING_MODE`, `AUDIT_SIGNING_KEY_ID`.
- Команды создания кейса/экспорта и ответы.
- Вывод `/events/verify` и `/exports/{id}/verify`.
- Вывод `SELECT signature, signature_alg, signing_key_id FROM processing_core.case_events ...`.
- Скрин/лог с `key_id` из `/api/core/v1/admin/audit/signing/keys`.

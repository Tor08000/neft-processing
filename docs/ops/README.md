# Ops documentation

## Trust Verification
- [Audit chain verification](audit_chain_verification.md)
- [Signature verification](signature_verification.md)
- [Object lock verification](object_lock_verification.md)

### Quick checklist for auditors
1. Сервис поднят через `docker compose up -d`, gateway отвечает на `http://localhost/health`.
2. Админ-токен получен через `POST /api/auth/login`.
3. Audit chain: `POST /api/v1/audit/verify` возвращает `status=OK`.
4. Audit chain: в `processing_core.audit_log` заполнены `prev_hash` и `hash`.
5. Audit chain: ручная проверка формулы хэша совпадает.
6. Audit immutability: UPDATE/DELETE `audit_log` возвращают ошибку `audit_log is immutable`.
7. Signatures: `/api/core/v1/admin/cases/<id>/events/verify` → `signatures.status=verified`.
8. Signatures: `/api/core/v1/admin/exports/<id>/verify` → `artifact_signature_verified=true`.
9. Object lock: `case_exports.locked_until` заполнен и `mc retention info` показывает retention.
10. Object lock: попытка удаления объекта возвращает `AccessDenied/ObjectLocked`.

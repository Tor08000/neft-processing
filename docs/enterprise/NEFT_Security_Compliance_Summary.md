# NEFT Security & Compliance Summary

**Audience:** CISO / Compliance Officer  
**Scope:** текущая реализация NEFT Platform (processing-core, admin UI, storage).

## 1. Security Posture Overview

- **Secure-by-design:** все изменения проходят через core-api и фиксируются в audit/case_events.
- **Defense in depth:** DB + hash chain + signature verification.
- **Zero silent mutation principle:** любые изменения формируют цепочку событий; нарушения целостности детектируются при verify.

## 2. Audit & Integrity

| Контроль | Реализация |
| --- | --- |
| Append-only logs | `case_events` защищены WORM-триггерами в Postgres |
| Tamper detection | `prev_hash → hash` цепочка для audit_log и case_events |
| Cryptographic proof | подписи hash chain для case_events (AuditSigningService) |
| Independent verification | `/api/v1/audit/verify` и `/cases/{case_id}/events/verify` |

## 3. Data Protection

| Тип данных | Защита |
| --- | --- |
| PII | Политическое маскирование в case_events и exports (email/phone/card/IBAN/ID) |
| Secrets | Полное маскирование ключей `password/token/secret/pin` в audit_log |
| Exports | Redaction перед сохранением + SHA-256 контроль содержания |
| Transit | Signed URLs (S3/MinIO) для скачивания экспортов |

## 4. Retention & WORM

- **Immutable audit core:** `case_events` WORM на уровне БД.
- **Retention policies:** `retention_until` для экспортов и вложений.
- **Legal hold:** блокирует purge на уровне org/case.
- **Purge with audit log:** `audit_purge_log` фиксирует все операции удаления экспорта.

## 5. Key Management

- **Local / KMS abstraction:** `local` (PEM) или `kms` (AWS KMS).
- **Key rotation support:** публичные ключи для прошлых ключей через `AUDIT_SIGNING_PUBLIC_KEYS_JSON`.
- **Fail-closed mode:** `AUDIT_SIGNING_REQUIRED=true` делает подпись обязательной.

## 6. Compliance Mapping (high level)

Без заявлений о сертификации, только соответствие архитектурным требованиям:

- **ISO 27001** — ✔️ контроль доступа, аудит, целостность журналов.
- **SOC 2** — ✔️ контроль изменений и неизменяемость критических событий.
- **GDPR** — ✔️ минимизация/маскирование/retention.
- **Financial audit readiness** — ✔️ воспроизводимые explain/diff + audit chain.

## 7. What We Do Not Claim

- Нет «black box AI».
- Нет «magic compliance».
- Все проверки воспроизводимы и проверяемы через hash chain + подписи.

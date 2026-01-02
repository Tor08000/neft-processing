# NEFT Platform Whitepaper (Enterprise)

## 1. Executive Summary

NEFT Platform — это инженерная платформа принятия решений, ориентированная на объяснимость, контроль человеческого фактора и аудируемость жизненного цикла решений. Система фиксирует контекст решения, действия оператора и цепочку событий в неизменяемой форме, позволяя воспроизводить историю и проверять целостность данных.

**Проблема, которую решает NEFT:**

- **Объяснимость решений.** Решения и их причины сохраняются в виде снимков (explain/diff/actions), которые можно восстановить и проверить.
- **Аудит.** Любое изменение состояния кейса фиксируется в событийной цепочке с вычисляемыми хэшами, а аудит-логи могут быть независимо проверены.
- **Контроль человеческого фактора.** Вся работа оператора с кейсом фиксируется в событиях, включая причины, изменения и артефакты.

**Целевая аудитория:**

- Enterprise
- Регулируемые отрасли
- Finance / Logistics / Energy / Gov-adjacent

## 2. Core Architecture Overview

### 2.1 High-level схема

```
Explain → Case → Audit → Hash Chain → Storage → Retention
```

### 2.2 Компоненты

- **core-api** (processing-core): сервис принятия решений, кейсов и аудита.
- **admin-ui**: интерфейс оператора/администратора.
- **storage**:
  - Postgres (основные данные: кейсы, события, аудит, метаданные экспорта).
  - S3/MinIO (экспортируемые артефакты: JSON экспорты, подписанные документы).

### 2.3 Trust boundaries (границы доверия)

```
[Admin UI] --(JWT/role)--> [core-api] --(DB)--> [Postgres]
                                |
                                +--(S3/MinIO, signed URLs)--> [Exports storage]
```

- Вся запись в аудит и кейсы проходит через core-api.
- Экспорты отдаются через time-bound signed URLs.

## 3. Explainability & Decision Lifecycle

### 3.1 Explain / Diff / Actions

- **Explain snapshot**: объяснение решения (json-снимок результата и причин).
- **Diff snapshot**: сравнение ожидаемого/фактического результата (для детерминированной проверки).
- **Actions**: зафиксированные решения/действия оператора.

### 3.2 Почему решения объяснимы

- Снимки explain/diff сохраняются в `case_snapshots`, а ссылки на них привязаны к кейсу.
- Для отдельных доменов объяснения сохраняются как `unified_explain_snapshots` с хэшем снимка.
- Любое изменение статуса кейса фиксируется как событие с хэшем и подписью.

### 3.3 Взаимодействие оператора

- Оператор видит explain/diff/selected actions в рамках кейса.
- Изменения статуса, назначение, закрытие и комментарии записываются как события кейса.
- Для каждой операции фиксируются `request_id` / `trace_id`, actor, временные метки.

## 4. Case Lifecycle

### 4.1 Создание кейса

- Кейс создаётся с explain/diff/selected actions и системным комментарием.
- Одновременно создаётся событие `CASE_CREATED` в цепочке кейса.

### 4.2 Работа с кейсом

- Изменение статуса, назначение, приоритет фиксируются в `case_events`.
- События содержат redacted payload (маскирование PII/секретов).

### 4.3 Закрытие кейса

- Закрытие фиксируется событием `CASE_CLOSED` с причиной/резолюцией.
- Связь с explain/diff/actions сохраняется через snapshots + события.

### 4.4 Почему кейс — ключевая единица аудита

- Все решения, изменения и экспортируемые артефакты привязаны к case_id.
- Верификация целостности проводится по цепочке событий кейса.

## 5. Audit & Tamper-Evident Design

### 5.1 Audit events

- Все ключевые операции формируют записи в `audit_log`.
- Аудит включает actor, timestamp, действие, before/after/diff и ссылки на внешние артефакты.

### 5.2 Hash chain

- В `audit_log` и `case_events` хранится `prev_hash → hash`.
- Хэш вычисляется сервером через canonical JSON сериализацию.
- Для case_events применяется дополнительное удаление редактируемых хэшей (`strip_redaction_hash`) для детерминизма.

### 5.3 Почему изменение событий обнаружимо

- Нарушение `prev_hash` или несоответствие `hash` детектируется через verify.
- Есть отдельные endpoint'ы для проверки целостности:
  - `/api/v1/audit/verify` (audit_log)
  - `/cases/{case_id}/events/verify` (case_events)

## 6. Cryptographic Attestation (Server Signatures)

### 6.1 Подпись hash chain

- `case_events` подписываются серверной подписью поверх хэша события.
- Подпись хранит `signature`, `signature_alg`, `signing_key_id`, `signed_at`.

### 6.2 Local signer vs KMS

- Поддерживаются режимы `local` (PEM ключи) и `kms` (AWS KMS).
- Алгоритмы: `ed25519`, `rsa_pss_sha256`, `ecdsa_p256_sha256`.

### 6.3 Проверка подписи

- Для каждого события доступна серверная проверка подписи.
- Проверка выполняется через audit signing service и привязанный ключ.

### 6.4 Публичные ключи

- Список публичных ключей доступен через конфигурацию (`AUDIT_SIGNING_PUBLIC_KEYS_JSON`).

### 6.5 Ротация ключей

- Поддерживаются активные и «retired» ключи; проверка подписей возможна для прошлых ключей.

## 7. Data Protection & Redaction

### 7.1 PII masking

- Для кейсов применяется контекстное маскирование: email, phone, PAN, IBAN, identifiers, адреса.
- Маскированные поля сохраняют hash-признак для сопоставления без раскрытия значения.

### 7.2 Secret redaction

- В `audit_log` автоматически маскируются поля, содержащие секреты (`password`, `token`, `secret`, `pin`).

### 7.3 Policy-driven approach

- Маскирование выполняется на уровне сервиса перед сохранением.

### 7.4 Почему в audit/export нет утечек

- Audit payload проходит mask + truncate (max 32KB).
- Exports сохраняются в виде редактированных JSON и не содержат исходных секретов.

## 8. Artifact Management (Exports)

- **Explain/Diff exports** создаются как case-export артефакты.
- Хранятся в S3/MinIO, доступ предоставляется через signed URL.
- Каждый экспорт имеет `content_sha256` и фиксируется в case_events (EXPORT_CREATED).

## 9. Retention, WORM & Legal Hold

### 9.1 Что хранится всегда

- `case_events` — WORM (write-once-read-many) на уровне базы (Postgres triggers).
- Audit chain сохраняется с `prev_hash → hash`.

### 9.2 Что удаляется по политике

- Экспорты и вложения имеют `retention_until` и могут быть удалены по политике.
- Удаление экспортов фиксируется в `audit_purge_log`.

### 9.3 Legal hold

- Поддерживаются legal holds на уровне org/case.
- Активный legal hold блокирует purge.

### 9.4 Audited purge

- Каждый purge фиксирует `purged_by`, policy, retention_days и причину.

### 9.5 Почему система готова к расследованиям

- История кейса восстанавливается по цепочке событий + подписей.
- Экспорты имеют SHA-256 и связаны с событиями.

## 10. Operational Guarantees

- **Append-only в ядре**: case_events неизменяемы (WORM-триггеры в Postgres).
- **Fail-closed signing**: при `AUDIT_SIGNING_REQUIRED=true` подпись обязательна, иначе операция завершается ошибкой.
- **Deterministic verification**: canonical JSON + hash chain.
- **No silent deletion (exports)**: любые удаления экспортов фиксируются в purge log.

## 11. Extensibility & Integration

- **KMS**: поддержка AWS KMS для подписи.
- **External audit**: verify endpoints для независимой проверки hash chain.
- **BI / Decision Memory**: export API + explain snapshots.
- **SIEM / SOC**: audit_log и case_events доступны для интеграции через API и прямые выгрузки.

## 12. Summary for Enterprise Buyers

**Ключевые отличия от типовых систем:**

- Hash-chain аудит + WORM для кейсов.
- Детальная объяснимость (explain/diff/actions) и фиксированный контекст.
- Криптографическая подпись цепочки событий.

**Почему NEFT снижает риски:**

- **Операционные:** каждое действие оператора фиксируется и проверяемо.
- **Регуляторные:** воспроизводимый аудит с независимой верификацией.
- **Human error:** решения и контекст сохранены, ошибки не скрываются.

# Документооборот v1 (B2B): что считаем «рабочим»

## 1) Пользовательский результат (Client Portal)

В `client-portal` должен быть раздел **«Документы»** с двумя вкладками.

### 1.1 Входящие (от NEFT клиенту)
Типы документов:
- оферта
- договор
- соглашения
- акты
- счета
- уведомления

Минимальная цепочка статусов:
`DRAFT -> SENT -> DELIVERED/IN_REVIEW -> SIGNED_CLIENT -> CLOSED` либо `REJECTED`.

### 1.2 Исходящие (от клиента в NEFT)
Типы документов:
- заявления
- письма
- заявки
- документы KYC
- запросы на лимиты
- рекламации

Минимальная цепочка статусов:
`DRAFT -> SENT -> DELIVERED -> IN_REVIEW -> CLOSED`.

## 2) Правила статусов ЭДО

- Статусы ЭДО хранятся в БД и обновляются независимо от UI.
- В dev допускается `MOCK`-провайдер, но статусная модель должна совпадать с prod-потоком.
- В prod запрещён «тихий mock» по умолчанию.
- Если EDO не настроен, документ получает `EDO_NOT_CONFIGURED`.
- Для `EDO_NOT_CONFIGURED` UI показывает понятное сообщение и fallback-действие: «Скачать PDF / подписать простым способом» (если разрешено политикой).

## 3) Модель данных v1 (processing-core)

### 3.1 `documents`
- `id UUID PK`
- `tenant_client_id`
- `direction ENUM(INBOUND, OUTBOUND)`
- `source ENUM(NEFT, CLIENT)`
- `category ENUM(CONTRACT, OFFER, ACT, INVOICE, KYC, LETTER, CLAIM, OTHER)`
- `title`
- `description nullable`
- `counterparty_name`
- `status ENUM(DRAFT, READY_TO_SEND, SENT, DELIVERED, IN_REVIEW, SIGNED_PLATFORM, SIGNED_CLIENT, REJECTED, CLOSED, ERROR, EDO_NOT_CONFIGURED)`
- `created_by_user_id nullable`
- `created_at`, `updated_at`

### 3.2 `document_files`
- `id`
- `document_id FK`
- `file_id/storage_key`
- `filename`, `mime`, `size`
- `sha256` (желательно)
- `created_at`

### 3.3 `document_signatures`
- `id`
- `document_id FK`
- `signer_side ENUM(PLATFORM, CLIENT, PARTNER)`
- `sign_method ENUM(SIMPLE_OTP, EDO_QES, UPLOAD_CERT, NONE)`
- `signed_at`
- `sign_payload_json` (минимум: `ip`, `user-agent`, `otp_tx_id`, `provider_doc_id`)
- `doc_hash`

### 3.4 `document_edostate`
- `id`
- `document_id FK`
- `provider ENUM(DIADOK, SBIS, KONTUR, MOCK)`
- `provider_message_id nullable`
- `provider_status`
- `last_polled_at`
- `error_code`, `error_message nullable`

### 3.5 `document_timeline`
- `id`
- `document_id FK`
- `event_type ENUM(CREATED, SENT, DELIVERED, VIEWED, SIGNED_PLATFORM, SIGNED_CLIENT, REJECTED, CLOSED, ERROR)`
- `actor_type ENUM(SYSTEM, USER)`
- `actor_id nullable`
- `meta_json`
- `created_at`

## 4) API v1 (Client Portal + Admin)

### 4.1 Client endpoints
- `GET /api/core/client/documents`
- `GET /api/core/client/documents/{id}`
- `GET /api/core/client/documents/{id}/download`
- `GET /api/core/client/documents/{id}/timeline`
- `POST /api/core/client/documents` (создать `OUTBOUND` в `DRAFT`)
- `POST /api/core/client/documents/{id}/upload`
- `POST /api/core/client/documents/{id}/submit` (в `READY_TO_SEND`)
- `POST /api/core/client/documents/{id}/send`
- `POST /api/core/client/documents/{id}/sign`

### 4.2 Admin endpoints
- `POST /api/core/admin/clients/{client_id}/documents` (создать `INBOUND` от NEFT)
- `POST /api/core/admin/documents/{id}/send`
- `POST /api/core/admin/documents/{id}/mark-signed-platform`

## 5) Интеграция EDO через integration-hub

Контракт между `processing-core` и `integration-hub`:
- `POST /api/int/edo/send` -> `provider_message_id`
- `GET /api/int/edo/{provider_message_id}/status` -> статус + ошибки

Обязанности `processing-core`:
- сохранять `document_edostate`
- писать события в `document_timeline`
- в prod блокировать send при mock/невалидной конфигурации EDO

## 6) План релизов (PR slicing)

- **PR-DOC-0**: каркас модуля (пустые списки, backend 200, ACL по `client_id`)
- **PR-DOC-1**: исходящие черновики + upload/download
- **PR-DOC-2**: timeline + внутренние статусы + submit
- **PR-DOC-3**: inbound от NEFT (admin create -> client sees)
- **PR-DOC-4**: send + EDO state + polling worker + prod guard
- **PR-DOC-5**: подпись клиентом + завершение документооборота
- **PR-DOC-6**: пакет выгрузки + уведомления

## 7) Definition of Done по итогам PR-DOC-5

Считаем v1 «рабочим», если одновременно выполнено:
1. Клиент может создать исходящий документ, загрузить файл, отправить и видеть статус/историю.
2. NEFT (через admin API) может создать входящий документ конкретному клиенту.
3. Для каждого документа есть timeline и понятные бизнес-статусы.
4. Статусы EDO сохраняются и обновляются (в dev через mock, в prod без «тихого» mock).
5. UI/worker не создают лог-штормов: есть backoff и лимиты частоты опроса.


## 8) Следующий логичный шаг: PR-13 (Email delivery)

Сразу после PR-DOC-5/6 рекомендуется выделить отдельный PR-13:
- **Email delivery через integration-hub** (отправка транзакционных писем без прямой связки UI -> SMTP).
- **Шаблон письма приглашения** в документооборот (локализация + brand tokens).
- **Одноразовая ссылка (one-time link)** с TTL и одноразовым потреблением для безопасного входа в сценарий подписания/просмотра.
- **Resend audit**: фиксировать каждую повторную отправку (кто инициировал, когда, канал, причина, correlation id).

Минимальные критерии готовности PR-13:
1. Письмо отправляется через integration-hub и имеет idempotency-key.
2. One-time link нельзя использовать повторно; истёкшие ссылки возвращают понятную ошибку.
3. Повторная отправка ограничена rate-limit/backoff и пишется в аудит.
4. В админ-интерфейсе/журнале доступна история отправок и resend-событий.

# NEFT Platform — AS-IS Architecture Freeze
## End of Core Development Stage

## 1. Executive Summary
Ядро платформы NEFT доведено до 250–300% готовности и зафиксировано как управляемый процессинговый центр, а не MVP или прототип. Архитектура намеренно ориентирована на объяснимость, управляемость и детерминизм, исключая «чёрные ящики» как принцип проектирования. Этот этап разработки официально завершён и признан архитектурно закрытым.

Core platform architecture is completed and frozen. Further work must proceed only through versioned extensions.

## 2. Архитектурный охват (AS-IS Scope)
Зафиксированное ядро включает следующие контуры:

* Financial Core (Ledger + Money Flow)
* Fuel Processing
* Logistics & Navigator
* CRM Control Plane
* Explain Layer
* Ops Workflow
* Fleet Intelligence & Control
* Decision / Assistant Stack
* Administrative UI (управленческий)

Это именно ядро платформы; периферийные продукты и внешние интеграции не входят в зафиксированный контур.

## 3. Зафиксированные архитектурные эталоны

### 3.1 Financial Core — Reference Implementation
Двойная запись, инварианты и детерминированность финансовых состояний обеспечивают воспроизводимость и объяснимость операций. Поддерживаются replay и explain как встроенные свойства финансовой модели. Enterprise-grade financial integrity закреплена как обязательный стандарт.

Financial Core is the immutable source of financial truth.

### 3.2 Fuel Processing — Hardened Spend Control
Полный контур authorize / settle / reverse реализован как единая транзакционная модель. Limits v2 работают в контекстных режимах, причины отказов канонизированы, explain-first дизайн встроен по умолчанию. Контур интегрирован с Money Flow.

### 3.3 Logistics & Navigator — Context Engine
Маршрутизация, ETA и отклонения фиксируются как контекстные события. Связка «маршрут ↔ топливо» встроена в доменную модель. Навигация организована через адаптеры и провайдер-агностичный слой.

### 3.4 CRM Control Plane — Policy Authority (Frozen)
Контрольная плоскость политики фиксирована как версионированная. Контракты и подписки v2 управляют использованием, пророццией и пакетами. Feature flags и риск/лимит-профили являются ядром управления. Политика freeze прописана явно.

CRM is a control plane, not a UI layer.

### 3.5 Explain Layer — Product-Level Capability
Единая explain-система определяет первичную причину и управляет реакциями. Поддержаны действия, SLA и эскалации, включая Ops inbox. Это продуктовая возможность, а не вспомогательная телеметрия.

Explainability is a first-class product feature.

### 3.6 Ops Workflow — Operational Governance
Операционная модель включает эскалации, SLA-трекинг и KPI по первичным причинам. Контур обеспечивает аудируемость действий и воспроизводимость операционных решений.

### 3.7 Fleet Intelligence & Control — Closed Loop System
Система фиксирует scores, тренды и инсайты, формирует предлагаемые действия и отслеживает эффект. Поддержаны decay, cooldown и confidence, а также обучение на результатах действий без ML.

### 3.8 Decision Stack / Assistant
Слой решения включает benchmarks, projections и What-If sandbox, а также Decision Memory. Контур предназначен для принятия решений CFO и Head of Ops.

Designed for CFO / Head of Ops decision-making.

## 4. Explicitly Deferred Capabilities (Intentional Non-Scope)
Следующие возможности сознательно исключены из ядра и остаются вне объёма:

* e-Signature providers
* EDI / Диадок / СБИС
* ERP integrations (1C, SAP)
* ML-heavy risk models (v5 in shadow)
* Mobile applications / UI polish

Deferred by design, architecture-ready.

## 5. Architecture Freeze Declaration
Архитектура ядра считается замороженной. Любые изменения возможны только через версионирование и создание новых контуров без модификации эталонных блоков. Money Flow, Ledger и Explain признаются immutable reference layers.

Core architecture is frozen. Any future development must extend, not modify, the existing core.

## 6. Forward Boundary
Дальнейшие работы относятся не к развитию ядра, а к выделению сервисов, интеграциям, продуктовым поверхностям и масштабированию.

## Stage Completion Addendum
Завершённые контуры, появившиеся после фиксации ядра (без пересмотра freeze):

* Webhooks v1.1 (integration-hub webhook self-service for the current partner portal flow: replay scheduling, pause/resume delivery, SLA calculations, alerts, metrics, partner UI controls via `/api/int/v1/webhooks/*`; processing-core helpdesk inbound webhooks remain a separate contour).
* BI export v1.1 (BI mart модели/агрегация, read-only BI API, CSV/JSONL exports + manifest, ClickHouse sync).
* Portals MAX (Client Portal MAX + Partner Portal MAX, i18n/UX polish).
* Marketplace events (contracts) + timeline readiness.
* PWA v1 (client portal companion: manifest/icon/sw, routing, push wiring, offline indicators).
* Support / Cases unified contour (canonical `cases` owner, `support_requests` compatibility tail, client helpdesk tickets case-linked).
* Client Controls v1 (limits/users/services/features tabs, role gating, confirmation modals).

## 7. Platform Capabilities — Implemented

| Capability | Status | Where in code | API endpoints | UI surfaces |
| --- | --- | --- | --- | --- |
| Explain v2 UX (sticky control bar, modes/tabs, empty/error/loading states, export/share, race-safe requests, query-state deep links) | ✅ done | `frontends/admin-ui/src/pages/ExplainPage.tsx`, `frontends/admin-ui/src/pages/explainQueryState.ts`, `frontends/admin-ui/src/index.css` | `GET /api/v1/admin/explain`, `GET /api/v1/admin/explain/diff`, `GET /api/v1/admin/explain/actions` | `/explain` |
| JsonViewer (search, collapse/expand, redaction-aware rendering) | 🟡 partial (no inline edit) | `frontends/admin-ui/src/components/common/JsonViewer.tsx`, `frontends/admin-ui/src/redaction/*` | — | multiple pages (`/explain`, `/cases/:id`, CRM/money details) |
| Cases lifecycle + close modal, status actions, exports list, decision history | ✅ done | `frontends/admin-ui/src/pages/cases/CasesListPage.tsx`, `frontends/admin-ui/src/pages/cases/CaseDetailsPage.tsx`, `frontends/admin-ui/src/components/cases/CloseCaseModal.tsx` | `POST /api/admin/cases/{id}/status`, `POST /api/admin/cases/{id}/close`, `GET /api/admin/cases/{id}/exports`, `GET /api/admin/cases/{id}/decisions` | `/cases`, `/cases/:id` |
| Audit timeline v2 (actor, field-level diff, trace/request id, artifacts, filters/search, synthetic fallback) | ✅ done | `frontends/admin-ui/src/pages/cases/CaseDetailsPage.tsx` | `GET /api/admin/cases/{id}/events` | `/cases/:id` → Audit timeline tab |
| Tamper-evident chain (client-side verify + highlighting + copy hashes) | ✅ done | `frontends/admin-ui/src/audit_chain/chain.ts`, `frontends/admin-ui/src/pages/cases/CaseDetailsPage.tsx` | — | `/cases/:id` → Audit timeline integrity banner |
| Server-side hash chain + verify | ✅ done | `platform/processing-core/app/services/case_events_service.py`, `platform/processing-core/app/routers/admin/cases.py` | `POST /api/admin/cases/{id}/events/verify` | `/cases/:id` (uses verify status) |
| Server signatures (local/KMS-compatible) + signing keys list | ✅ done | `platform/processing-core/app/services/audit_signing.py`, `platform/processing-core/app/services/case_events_service.py`, `platform/processing-core/app/routers/admin/audit.py` | `GET /api/admin/audit/signing/keys` | `/cases/:id` (signature status in decision history) |
| WORM exports (S3/MinIO) + signed URLs | ✅ done | `platform/processing-core/app/services/export_storage.py`, `platform/processing-core/app/services/case_export_service.py`, `platform/processing-core/app/routers/admin/exports.py` | `POST /api/admin/exports`, `POST /api/admin/exports/{id}/download` | `/cases/:id` → Exports list |
| Signed artifacts + export verify | ✅ done | `platform/processing-core/app/services/case_export_verification_service.py`, `platform/processing-core/app/routers/admin/exports.py` | `POST /api/admin/exports/{id}/verify` | `/cases/:id` (export verification) |
| Retention + legal hold + purge log | ✅ done | `platform/processing-core/app/services/audit_retention_service.py`, `platform/processing-core/app/services/audit_purge_service.py`, `platform/processing-core/app/models/audit_retention.py`, `platform/processing-core/app/cli.py` | `POST /api/admin/audit/legal-holds`, `POST /api/admin/audit/legal-holds/{id}/disable`, `GET /api/admin/audit/legal-holds` | — (API/CLI) |
| Redaction policy (UI + server) | ✅ done | `frontends/admin-ui/src/redaction/*`, `platform/processing-core/app/services/case_event_redaction.py` | — | `/cases/:id` (audit timeline tooltips), `/explain` (masked JSON) |
| Decision Memory (history + audit linkage) | ✅ done | `platform/processing-core/app/models/decision_memory.py`, `platform/processing-core/app/services/decision_memory/*`, `platform/processing-core/app/routers/admin/cases.py` | `GET /api/admin/cases/{id}/decisions` | `/cases/:id` → Decision History tab |
| Mastery / Gamification (score badges, confidence/penalty, streaks, achievements, levels) | ✅ done | `frontends/admin-ui/src/gamification/*`, `frontends/admin-ui/src/mastery/*`, `frontends/admin-ui/src/pages/ExplainPage.tsx` | — | `/explain` control bar + summary cards |

## 8. Data Model AS-IS

Основные сущности audit-контура:

```
cases
  ├─ case_events (append-only, seq, prev_hash/hash, signature*)
  │    └─ decision_memory (WORM, audit_event_id → case_events.id)
  ├─ case_exports (object_key, content_sha256, artifact_signature*, retention_until)
  ├─ audit_legal_holds (scope: case/global, active)
  └─ audit_purge_log (purged_at, purged_by, policy)
```

Ключевые связи и атрибуты:

* `case_events` — append-only цепочка с `seq`, `prev_hash`, `hash`, `payload_redacted`, `signature*` (`platform/processing-core/app/models/cases.py`).
* `case_exports` — экспорт с `object_key`, `content_sha256`, подписью артефакта и `retention_until` (`platform/processing-core/app/models/case_exports.py`).
* `decision_memory` — записи решений, привязанные к `case_events.id` и снапшотам (`platform/processing-core/app/models/decision_memory.py`).
* `audit_legal_holds` / `audit_purge_log` — WORM/retention и журнал очисток (`platform/processing-core/app/models/audit_retention.py`).

## 9. Security & Audit Posture AS-IS

* Append-only гарантия: `case_events` и `decision_memory` защищены WORM-триггерами на UPDATE/DELETE (алембик миграции `20291780_0095_audit_retention_worm.py`, `20291810_0097_decision_memory_audit.py`).
* Tamper detection: хэш-цепочка на backend (`verify_case_event_chain`) + клиентская проверка и UI-индикаторы (`frontends/admin-ui/src/audit_chain/chain.ts`).
* Cryptographic attestation: подписи событий/артефактов через `AuditSigningService` (local/KMS), ключи доступны через `/api/admin/audit/signing/keys`.
* Redaction (PII/secrets): серверная редация в `case_event_redaction.py` + UI-маскирование/tooltip в `frontends/admin-ui/src/redaction/*`.
* Retention/WORM/Legal hold: legal hold API + purge лог (`audit_retention_service.py`, `audit_purge_service.py`).
* Export storage controls: S3/MinIO + signed URLs (`export_storage.py`, `/api/admin/exports/{id}/download`).
* Что проверяют endpoint’ы:
  * `/api/admin/cases/{id}/events/verify` — целостность цепочки + подписи событий.
  * `/api/admin/exports/{id}/verify` — SHA256 содержимого, подпись артефакта, связь с audit-цепочкой.

## 10. Operational Notes / Runbooks

Env vars (минимум для audit-контура):

* `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_EXPORTS`, `S3_REGION`, `S3_SIGNED_URL_TTL_SECONDS`, `S3_EXPORTS_PREFIX` (`shared/python/neft_shared/settings.py`).
* `AUDIT_EXPORT_RETENTION_DAYS`, `AUDIT_ATTACHMENT_RETENTION_DAYS`, `AUDIT_CACHE_RETENTION_DAYS`.
* `AUDIT_SIGNING_MODE`, `AUDIT_SIGNING_REQUIRED`, `AUDIT_SIGNING_ALG`, `AUDIT_SIGNING_KEY_ID`,
  `AUDIT_SIGNING_PRIVATE_KEY_B64`, `AUDIT_SIGNING_PUBLIC_KEYS_JSON`.

Checks / smoke:

* DB migrations: `alembic upgrade head` (core-api).
* Purge CLI (retention): `python -m app.cli audit_purge --dry-run`.
* Hash/signature tests:
  * `pytest platform/processing-core/app/tests/test_case_events_hash_chain.py`
  * `pytest platform/processing-core/app/tests/test_case_events_signatures.py`
  * `pytest platform/processing-core/app/tests/test_case_exports_storage.py`
  * `pytest platform/processing-core/app/tests/test_decision_memory_audit.py`

Pytest runbook (docker/local):

* Docker compose (use service network + DATABASE_URL_TEST):
  * `docker compose run --rm core-api env DATABASE_URL_TEST=postgresql+psycopg://neft:neft@postgres:5432/neft pytest platform/processing-core/app/tests/test_settlement_v1.py -q`
* Local (override test DB):
  * `export DATABASE_URL_TEST=postgresql+psycopg://neft:neft@127.0.0.1:5432/neft_test`
  * `pytest platform/processing-core/app/tests/test_settlement_v1.py -q`

## 11. Operational Readiness AS-IS

**Scope:** Billing / Reconciliation / Settlement.

* Alerts: planned (spec defined, wiring pending).
* SLO: defined in `docs/ops/operational_readiness_finance.md`.
* Runbooks: available in `docs/runbooks/` (billing/reconciliation/settlement).

## 12. Readiness / Stage Completion

| Domain | Target | AS-IS | Gaps | Next actions |
| --- | --- | --- | --- | --- |
| Explain → Case → Audit → Retention → Exports | Enterprise audit core | ✅ Completed (UI + API + storage + verification) | — | Scale testing, perf baselines |
| Signatures / Key management | KMS-ready | ✅ Local + KMS-compatible | Cloud KMS integration wiring | Configure production KMS and key rotation |
| Storage WORM | Immutable storage | ✅ Logical WORM + retention | Storage-level Object Lock (optional) | Enable MinIO/S3 Object Lock if required |
| Monitoring | Integrity/retention alerts | 🟡 Partial (verify endpoints, purge logs) | Alerts for verify/purge failures | Wire metrics + alerting |
| Documentation/Compliance | Enterprise artifacts | ✅ Whitepaper + Security Summary | — | Keep in sync with release notes |

## 13. Current Stage / What’s next

**Current stage:** Enterprise-audit core готов (Explain → Case → Audit → Retention → Exports → Signatures → Decision Memory контур закрыт).

**Remaining (planned)**

* Production hardening инфраструктуры: реальный KMS-провайдер, MinIO/S3 Object Lock (Governance), алерты по verify/purge failures.
* Доменные контуры вне audit-контура: billing/ledger invariants, marketplace/CRM/logistics (если целевой UPAS требует полный охват).
* Product UX/Branding: клиентский web UX/branding/юзабилити (если в планах).

**Next stage:** Enterprise Audit Core завершён → переходим в Operational Readiness + Product UX/Branding + Domain completion (Billing/Ledger/Marketplace).

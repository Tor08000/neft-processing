# NEFT AS-IS Readiness Current (main branch alignment)

Дата аудита: 2026-02-16.
Источник: фактический код/конфиги репозитория (`platform/*`, `frontends/*`, `gateway/*`, `shared/*`, `scripts/*`, `.github/workflows/*`, `docker-compose*.yml`).

## 1) Технический аудит (код ↔ runtime-конфигурация)

### 1.1 Scope проверки

Проверены:
- сервисы платформы и роутеры (`platform/*`),
- фронтенды и e2e (`frontends/*`),
- gateway-маршрутизация (`gateway/*`),
- shared-библиотеки (`shared/*`),
- smoke/verify/gate-скрипты (`scripts/*`),
- CI workflows (`.github/workflows/*`),
- compose-профили (`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.test.yml`, `docker-compose.smoke.yml`),
- Alembic-цепочки для `auth-host` и `processing-core`.

### 1.2 Stub / mock / placeholder (обнаружено)

Ниже — заглушки и mock-пути, влияющие на поведение среды.

| Файл | Строка | Тип заглушки | Влияет на prod? |
|---|---:|---|---|
| `docker-compose.dev.yml` | 5 | `LOGISTICS_PROVIDER=mock` | Нет (только dev override) |
| `platform/crm-service/app/main.py` | 1 | CRM сервис реализован как compatibility/shadow surface, не как canonical owner | Да (если включён сервис в prod профиле) |
| `platform/processing-core/app/integrations/fuel/providers/stub_provider.py` | 1 | Fuel provider stub | Да (если выбран провайдером) |
| `platform/processing-core/app/services/bank_stub_service.py` | 1 | Bank stub service | Да (если вызван сценарий bank stub) |
| `platform/processing-core/app/services/erp_stub_service.py` | 1 | ERP stub service | Да (если вызван сценарий ERP stub) |
| `platform/processing-core/app/services/legal_integrations/edo/sbis.py` | 10 | `NotImplementedError` в SBIS adapter | Да |
| `platform/processing-core/app/services/legal_integrations/edo/diadok.py` | 10 | `NotImplementedError` в Diadok adapter | Да |
| `platform/processing-core/app/services/legal_integrations/providers/docusign.py` | 10 | `NotImplementedError` в DocuSign adapter | Да |
| `platform/processing-core/app/services/legal_integrations/providers/kontur_sign.py` | 10 | `NotImplementedError` в Kontur.Sign adapter | Да |
| `platform/processing-core/app/services/helpdesk_service.py` | 89 | `NotImplementedError` интерфейса | Да |
| `platform/processing-core/app/services/unified_rules_engine.py` | 61 | `NotImplementedError` | Да |
| `platform/document-service/app/settings.py` | 24 | `PROVIDER_X_MODE=real` по умолчанию, explicit `mock/degraded/disabled` modes | Да |
| `platform/document-service/app/sign/providers/provider_x.py` | 92 | mock signature flow | Да |
| `platform/logistics-service/neft_logistics_service/providers/mock.py` | 20 | Полный mock provider | Да (если `LOGISTICS_PROVIDER=mock`) |
| `platform/integration-hub/neft_integration_hub/settings.py` | 44 | historical `DIADOK_MODE=mock` default was removed; current defaults are real/degraded/disabled | Нет |
| `platform/integration-hub/neft_integration_hub/providers/diadok.py` | 23 | mock request id | Да |
| `scripts/smoke_gating_states.cmd` | 7 | aggregated gating smoke over mounted owner states | Да (used in runtime verification for auth/onboarding/overdue gating) |
| `.github/workflows/cd.yml` | 10 | `Deploy placeholder` | Нет (CD заглушка) |

Примечание: полный машинный поиск по ключам `stub/mock/NotImplemented/TODO/placeholder/fake/demo-only` также захватывает UI-placeholder поля форм и тестовые `vi.mock`; они не классифицированы как prod-блокер.

### 1.3 Optional imports и «тихое» отключение функционала

#### Обнаруженные optional import-механизмы

1. `processing-core` использует `import_router(...)` с DEV-режимом optional модулей (`return None`) и PROD fail-fast (`raise`).
2. Динамически optional подключаются роутеры из `OPTIONAL_ENDPOINT_ROUTERS` (intake, partners, billing_invoices, payouts, fuel/logistics/edo/bi/commercial/support).
3. Точечные `try: from ... import ... except Exception` найдены в admin billing PDF задачах (`run_monthly_invoices_task`, `generate_invoice_pdf`) — при ошибке импортов API вернёт runtime ошибку, но сервис стартует.

#### Риск «роутер тихо не включился»

- В DEV профиле: возможен (optional endpoint-модуль пропущен и роутер не регистрируется).
- В PROD профиле (`APP_ENV=prod`): `import_router` работает в strict режиме и должен падать на import error (fail-fast).

### 1.4 Миграции (Alembic)

Проверено:
- в CI есть обязательный gate `scripts/ci/gate_migrations.sh` (single-head + `upgrade head` для `auth-host` и `processing-core`),
- `ci.yml` дополнительно проверяет uniqueness/protected revisions и `upgrade head` в smoke контуре.

Обнаружено:
- локальный запуск `python scripts/check_alembic_history.py` падает на `ModuleNotFoundError: alembic_helpers` при загрузке миграции `0039_billing_finance_idempotency.py`; это означает, что часть локальных «исторических» проверок ревизий не воспроизводится без дополнительного PYTHONPATH/рефакторинга импортов миграции.

Вывод по состоянию:
- дисциплина single-head в CI реализована,
- есть технический долг в оффлайн-скрипте проверки истории.

### 1.5 Compose профили и поведение по умолчанию

- `docker-compose.yml` маркирует основные сервисы профилями `prod` и `dev` (postgres, redis, auth-host, core-api, integration-hub, logistics-service, workers, beat, gateway и др.).
- Default ENV в прод-профиле:
  - `APP_ENV=${APP_ENV:-prod}`,
  - `USE_STUB_CRM/USE_STUB_EDO/USE_MOCK_LOGISTICS` по умолчанию `0`,
  - но в стеке присутствуют сервисы, содержащие stub/mock реализации.
- `docker-compose.dev.yml` явно принудительно включает mock logistics (`LOGISTICS_PROVIDER=mock`, `USE_MOCK_LOGISTICS=1`).

### 1.6 CI coverage (факт)

- Есть unified PR gate: `.github/workflows/ci-gate.yml`.
- В gate есть lint/typecheck, unit tests, migrations, compose-prod-e2e.
- Есть gateway e2e smoke (`scripts/ci/gate_e2e_smoke.sh`) и playwright smoke (`scripts/ci/gate_playwright_smoke.sh`).
- Миграции проверяются отдельным job и дополнительным smoke workflow.
- Frontends проверяются lint/typecheck для `admin-ui`, `client-portal`, `partner-portal`.

## 2) NEFT_ASIS_Readiness_Current

| Сервис | Статус | Prod Ready | Dev Only | Stub | Блокер |
|---|---|---|---|---|---|
| gateway | OK | Да | Нет | Нет | Нет |
| auth-host | OK | Да | Нет | Нет | Нет |
| processing-core | Partial | Частично | Нет | Частично (интеграционные адаптеры) | Есть (незакрытые NotImplemented-пути) |
| integration-hub | Partial | Частично | Нет | Только explicit mock mode | Есть (не все реальные transport adapters wired) |
| logistics-service | Partial | Частично | Нет | Да (mock provider) | Есть (mock fallback) |
| document-service | Partial | Частично | Нет | Только explicit mock/degraded modes | Есть (реальный provider требует config, degraded mode now explicit) |
| crm-service | Partial | Нет (не canonical owner) | Да | Да (compatibility/shadow) | Да |
| workers/beat | OK | Да | Нет | Нет | Нет |
| admin-ui | Partial | Частично | Нет | Нет | Нет |
| client-portal | Partial | Частично | Нет | Нет | Нет |
| partner-portal | Partial | Частично | Нет | Только explicit demo mode (`VITE_DEMO_MODE`), без implicit prod bypass | Есть (широкая runtime parity/capability rollout ещё не завершена) |

Статусы строго из набора: `OK`, `Partial`, `Dev-Only`, `Stub`, `Broken`.

## 3) Architecture Map (обновлённая)

### 3.1 Service map

- **Gateway (Nginx)** — единая входная точка (`/health`, `/api/*`, `/admin/`, `/client/`, `/partner/`).
- **Auth flow**: SPA/API client → `gateway` → `auth-host` (`/api/auth/*` или legacy `/api/v1/auth/*`) → JWT.
- **Domain API flow**: client/admin/partner token → `gateway` → `processing-core` (`/api/core/*`).
- **Integration flow**:
  - `processing-core` ↔ `integration-hub` (webhooks + EDO transport with explicit mock/degraded modes),
  - `processing-core` ↔ `logistics-service` (provider switch: integration_hub/mock),
  - `processing-core` ↔ `document-service` (PDF/sign verify),
  - async задачи через `workers/beat` + Redis.

### 3.2 Gateway routing

- `/api/core/*` → core-api,
- `/api/auth/*` (+ legacy `/api/v1/auth/*`) → auth-host,
- `/api/int/*`/`/api/integrations/*` → integration-hub,
- `/api/logistics/*` → logistics-service,
- `/api/docs/*` → document-service,
- `/admin/`, `/client/`, `/partner/` → соответствующие SPA.

### 3.3 Domain boundaries

- **Identity/Security**: auth-host + security-модули processing-core.
- **Core operations/finance/legal**: processing-core.
- **External integrations**: integration-hub, logistics-service, document-service.
- **Presentation layer**: три портала (admin/client/partner).

### 3.4 Event flow

- Асинхронные доменные процессы и расписания проходят через Celery (`workers`, `beat`) с Redis broker/backend.
- Webhook intake/delivery/retry реализован в integration-hub.

## 4) Production Profile Specification

### PROD PROFILE RULES

1. Mock provider запрещён.
2. Stub provider запрещён.
3. Optional imports, скрывающие отключение функционала, запрещены для prod-path.
4. Fail-fast обязателен (`APP_ENV=prod` strict import mode).
5. Миграции обязательны (single head + `upgrade head` как gate).
6. CI gate обязателен для merge.

### PROD текущий факт

- Правила fail-fast и migration gate реализованы.
- Полное соответствие «no mock/no stub» **не достигнуто**: в runtime-коде присутствуют mock/stub интеграции, но production defaults уже сдвинуты в explicit real/degraded/disabled modes вместо mock-by-default.

## 5) DEV Profile Specification

### DEV PROFILE RULES

1. Mock разрешён.
2. Stub разрешён.
3. Optional imports допустимы.
4. Verbose logs допустимы.
5. Demo seed разрешён.

### DEV текущий факт

- `docker-compose.dev.yml` включает mock logistics.
- В auth/core доступны demo bootstrap/seed сценарии.
- Optional endpoints допускают пропуск в DEV через `import_router`.

## 6) Security Status

| Контроль | Статус |
|---|---|
| JWT configuration | Реализовано (auth-host + маршрутизация через gateway) |
| Refresh token rotation | Обнаружено частично (нужна точечная валидация полного lifecycle в отдельном security-аудите) |
| Revocation | Обнаружено частично |
| SSO | Реализовано частично (SSO routes присутствуют в auth-host) |
| Tenant isolation | Реализовано частично (multi-tenant migration присутствует в auth-host) |
| Rate limits | Требует доработки как единая cross-service политика |
| Audit trail | Реализовано (audit/trust модули и отдельные trust-gates в CI) |

## 7) Integration Status

| Интеграция | Реальная | Stub | Prod-ready |
|---|---|---|---|
| CRM | Частично (canonical admin CRM в `processing-core`) | Да (`crm-service` compatibility/shadow surface) | Нет |
| Logistics | Частично (integration_hub provider path) | Да (`mock` provider) | Частично |
| EDO | Частично | Да (explicit integration-hub transport with mock only by mode and degraded unsupported providers) | Нет |
| ERP-light | Частично | Да (`erp_stub_service`) | Нет |

## 8) CI/CD Status

| Проверка | Статус |
|---|---|
| Unified PR gate | Реализовано (`ci-gate.yml`) |
| e2e smoke через gateway | Реализовано (`gate_e2e_smoke.sh`) |
| Playwright smoke | Реализовано (`gate_playwright_smoke.sh`) |
| Migration verification | Реализовано (`gate_migrations.sh` + smoke migration jobs) |
| Compose prod sanity check | Реализовано (`gate_compose_up.sh`) |

## 9) Нормализация формулировок (исторические оценки)

В этой версии документации использованы только формулировки:
- **проверено**,
- **обнаружено**,
- **требует доработки**,
- **реализовано**.

Оценки в процентах и предположительные формулировки не используются.

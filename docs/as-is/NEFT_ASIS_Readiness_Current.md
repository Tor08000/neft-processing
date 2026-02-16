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

| Файл | Строка | Тип заглушки | Влияет на prod? |
|---|---:|---|---|
| `docker-compose.dev.yml` | 5 | `LOGISTICS_PROVIDER=mock` | Нет (только dev override) |
| `platform/crm-service/app/main.py` | 1 | CRM сервис реализован как stub-микросервис | Да |
| `platform/processing-core/app/integrations/fuel/providers/stub_provider.py` | 1 | Fuel provider stub | Да |
| `platform/processing-core/app/services/bank_stub_service.py` | 1 | Bank stub service | Да |
| `platform/processing-core/app/services/erp_stub_service.py` | 1 | ERP stub service | Да |
| `platform/processing-core/app/services/helpdesk_service.py` | 89 | `NotImplementedError` интерфейса | Да |
| `platform/processing-core/app/services/legal_integrations/edo/sbis.py` | 10 | `NotImplementedError` в SBIS adapter | Да |
| `platform/processing-core/app/services/legal_integrations/edo/diadok.py` | 10 | `NotImplementedError` в Diadok adapter | Да |
| `platform/document-service/app/settings.py` | 24 | `PROVIDER_X_MODE=mock` default | Да |
| `platform/logistics-service/neft_logistics_service/providers/mock.py` | 20 | Полный mock provider | Да |
| `platform/integration-hub/neft_integration_hub/settings.py` | 41 | `DIADOK_MODE=mock` default | Да |
| `platform/integration-hub/neft_integration_hub/providers/diadok.py` | 23 | mock request id | Да |
| `platform/processing-core/app/routers/client_portal_v1.py` | 358 | `stub://` URL fallback | Да |
| `frontends/partner-portal/src/components/AccessGate.tsx` | 278 | `Demo-only bypass` | Да |
| `.github/workflows/cd.yml` | 10 | `Deploy placeholder` | Нет |

Примечание: машинный поиск по ключам `stub/mock/NotImplemented/TODO/placeholder/fake/demo-only` дополнительно находит UI placeholder-поля и тестовые `mock`-конструкции, они не классифицированы как prod-блокер.

### 1.3 Optional imports и «тихое» отключение функционала

Обнаружено:
1. `processing-core` использует `import_router(...)` с DEV-режимом optional модулей (`return None`) и PROD fail-fast (`raise`).
2. Optional роутеры подключаются через `OPTIONAL_ENDPOINT_ROUTERS`.
3. Точечные `try: from ... import ... except Exception` найдены в admin billing PDF задачах.

Вывод:
- В DEV профиле «тихое» отключение возможно.
- В PROD профиле (`APP_ENV=prod`) импорт роутеров работает в strict fail-fast режиме.

### 1.4 Миграции (Alembic)

Проверено:
- в CI есть `scripts/ci/gate_migrations.sh` (single-head + `upgrade head` для `auth-host` и `processing-core`),
- в `ci.yml` есть проверки revision uniqueness/protected revisions и `upgrade head`.

Обнаружено:
- локальный `python scripts/check_alembic_history.py` падает на `ModuleNotFoundError: alembic_helpers` при загрузке `0039_billing_finance_idempotency.py`.

Вывод:
- migration discipline в CI реализована,
- локальный оффлайн-скрипт истории требует доработки среды/импортов.

### 1.5 Compose профили

- В `docker-compose.yml` ключевые сервисы идут профилями `prod` и `dev`.
- Значения по умолчанию: `APP_ENV=prod`, `USE_STUB_CRM=0`, `USE_STUB_EDO=0`, `USE_MOCK_LOGISTICS=0`.
- В `docker-compose.dev.yml` mock logistics включён явно (`LOGISTICS_PROVIDER=mock`, `USE_MOCK_LOGISTICS=1`).

### 1.6 CI покрытие

Проверено:
- есть unified PR gate (`ci-gate.yml`),
- есть gateway e2e smoke,
- есть playwright smoke,
- есть migration verification,
- есть compose prod sanity check.

---

## 2) NEFT_ASIS_Readiness_Current

| Сервис | Статус | Prod Ready | Dev Only | Stub | Блокер | Что нужно для OK |
|---|---|---|---|---|---|---|
| gateway | OK | Да | Нет | Нет | Нет | Поддерживать текущий CI + health routing без regressions |
| auth-host | OK | Да | Нет | Нет | Нет | Поддерживать security regression tests и миграционную дисциплину |
| processing-core | Partial | Частично | Нет | Частично | Да | Закрыть `NotImplemented` в helpdesk/edo adapters; убрать `stub://` fallback в prod-path; зафиксировать strict no-stub policy тестами |
| integration-hub | Partial | Частично | Нет | Да | Да | Убрать default mock DIADOK режим; реализовать реальные провайдерные адаптеры; добавить e2e контрактные тесты реального dispatch/status |
| logistics-service | Partial | Частично | Нет | Да | Да | Отключить mock как runtime fallback в prod; ввести hard-fail при недоступном real provider; добавить prod smoke без mock |
| document-service | Partial | Частично | Нет | Да | Да | Убрать `PROVIDER_X_MODE=mock` default для prod; реализовать боевой подпись/verify адаптер; покрыть интеграционными тестами |
| crm-service | Stub | Нет | Да | Да | Да | Убрать stub-сервис; реализовать CRUD + audit trail; добавить миграции; покрыть unit/integration tests; включить в prod profile как полноценный сервис |
| workers/beat | OK | Да | Нет | Нет | Нет | Поддерживать стабильность очередей и smoke replay сценарии |
| admin-ui | Partial | Частично | Нет | Нет | Нет | Зафиксировать E2E smoke ключевых админ-потоков через gateway |
| client-portal | Partial | Частично | Нет | Нет | Нет | Зафиксировать E2E smoke клиентского контура (login → core endpoints) |
| partner-portal | Partial | Частично | Нет | Да | Да | Убрать `Demo-only bypass` из prod path; закрепить profile-aware отключение в сборке/ENV; добавить smoke на запрет bypass в prod |

Статусы строго из набора: `OK`, `Partial`, `Dev-Only`, `Stub`, `Broken`.

---

## 3) 🔴 PROD BLOCKERS (текущие)

Без интерпретаций, только текущие блокеры production-clean профиля:
- CRM stub (`crm-service`),
- EDO mock default (`DIADOK_MODE=mock`),
- ERP stub (`erp_stub_service`),
- Helpdesk `NotImplemented`,
- `provider_x` mock default в document-service,
- integration-hub `DIADOK_MODE=mock` default,
- partner-portal `demo-only bypass`,
- bank stub (`bank_stub_service`).

---


## 3.1) Severity приоритизация блокеров

| Блокер | Severity |
|---|---|
| CRM stub (`crm-service`) | High |
| EDO mock default (`DIADOK_MODE=mock`) | Critical |
| ERP stub (`erp_stub_service`) | High |
| Helpdesk `NotImplemented` | Medium |
| `provider_x` mock default в document-service | High |
| partner-portal `demo-only bypass` | Critical |
| bank stub (`bank_stub_service`) | High |

## 4) Architecture Map (обновлённая)

### 4.1 Service map
- Gateway (Nginx) — единая входная точка (`/health`, `/api/*`, `/admin/`, `/client/`, `/partner/`).
- Auth flow: SPA/API client → gateway → auth-host → JWT.
- Domain flow: client/admin/partner token → gateway → processing-core (`/api/core/*`).
- Integrations: processing-core ↔ integration-hub/logistics/document-service.
- Async: Celery (`workers`, `beat`) + Redis.

### 4.2 Gateway routing
- `/api/core/*` → core-api,
- `/api/auth/*` (+ legacy `/api/v1/auth/*`) → auth-host,
- `/api/int/*` и `/api/integrations/*` → integration-hub,
- `/api/logistics/*` → logistics-service,
- `/api/docs/*` → document-service,
- `/admin/`, `/client/`, `/partner/` → SPA.

### 4.3 Domain boundaries
- Identity/Security: auth-host + security модули processing-core.
- Core operations/finance/legal: processing-core.
- External integrations: integration-hub/logistics/document.
- Presentation: admin/client/partner portals.

---

## 5) Реальный уровень зрелости (по коду)

| Область | Зрелость |
|---|---|
| Identity | Зрелая |
| Gateway | Зрелая |
| Core domain | Зрелая |
| Integration layer | Незавершён |
| CRM | Отсутствует как production-ready домен |
| ERP-light | Отсутствует как production-ready интеграция |
| Enterprise security controls | Частично |
| Multi-tenant | Частично |

---

## 6) Production Profile Specification

### PROD PROFILE RULES
1. Mock provider запрещён.
2. Stub provider запрещён.
3. Optional imports, скрывающие отключение prod-функционала, запрещены.
4. Fail-fast обязателен.
5. Миграции обязательны.
6. CI gate обязателен.

### PROD текущий факт
- Fail-fast и migration gate реализованы.
- **Production profile is NOT clean yet.**
- **NO MOCK / NO STUB / FAIL FAST** как целевой enterprise-профиль ещё не достигнут в полном объёме.

---

## 7) DEV Profile Specification

### DEV PROFILE RULES
1. Mock разрешён.
2. Stub разрешён.
3. Optional imports допустимы.
4. Verbose logs допустимы.
5. Demo seed разрешён.

### DEV текущий факт
- `docker-compose.dev.yml` явно включает mock logistics.
- Demo bootstrap/seed сценарии доступны.
- Optional endpoints могут быть пропущены в DEV.

---

## 8) Security Status

| Контроль | Статус |
|---|---|
| JWT configuration | Реализовано |
| Refresh rotation | Обнаружено частично |
| Revocation | Обнаружено частично |
| SSO | Реализовано частично |
| Tenant isolation | Реализовано частично |
| Rate limits | Требует доработки |
| Audit trail | Реализовано |

## 9) Integration Status

| Интеграция | Реальная | Stub | Prod-ready |
|---|---|---|---|
| CRM | Частично | Да | Нет |
| Logistics | Частично | Да | Частично |
| EDO | Частично | Да | Нет |
| ERP-light | Частично | Да | Нет |

## 10) CI/CD Status

| Проверка | Статус |
|---|---|
| Unified PR gate | Реализовано |
| e2e smoke через gateway | Реализовано |
| Playwright smoke | Реализовано |
| Migration verification | Реализовано |
| Compose prod sanity check | Реализовано |

## 11) Нормализация формулировок

В документе использованы формулировки:
- **проверено**,
- **обнаружено**,
- **требует доработки**,
- **реализовано**.

Проценты готовности и «предположительно» не используются.


---

## 12) Enterprise Clean Gap

Чтобы production-profile стал enterprise-grade, требуется:
- убрать все runtime mock defaults,
- запретить demo bypass в prod сборке,
- закрыть `NotImplemented` в интеграционных адаптерах,
- зафиксировать SSO/refresh lifecycle тестами,
- включить provider availability health-check на startup.

## 13) Target State (v1 Enterprise Clean)

- No runtime mock paths in prod.
- All integrations fail-fast if misconfigured.
- No stub services in prod profile.
- All portals covered by gateway e2e smoke.
- Single compose prod profile reproducible.

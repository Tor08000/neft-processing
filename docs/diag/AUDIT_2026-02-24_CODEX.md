# NEFT Platform — Full Repo Audit + Execution Proof (2026-02-24)

## 2.1 Executive Summary
1. MVP runtime подтверждён частично: Python-модули компилируются, локальные тесты (integration-hub + logistics + document-service) проходят, FastAPI app-реестры доступны для части сервисов.
2. Полный runtime stack НЕ подтверждён: в среде отсутствует Docker CLI (`docker compose` недоступен), поэтому end-to-end межсервисный smoke не выполнен.
3. Главный инфраструктурный блокер: `alembic heads` в `processing-core` падает без явного `PYTHONPATH` (ошибка `ModuleNotFoundError: alembic_helpers`).
4. После добавления `PYTHONPATH` (`platform/processing-core` + `shared/python`) `alembic heads` выполняется и показывает 2 head revision.
5. `alembic upgrade head` на SQLite падает на `CREATE SCHEMA` (PostgreSQL-специфичная логика в `alembic/env.py`), поэтому миграции проверены только частично (parse/history/heads).
6. По static execution-map найдено большое количество runtime-путей с mock/stub провайдерами (integration-hub, logistics-service, document-service, processing-core fuel/integrations).
7. В auth-host и ai-risk-scorer OpenAPI генерируется, но есть warning о duplicate operation IDs (не блокер запуска, но риск контрактной неоднозначности).
8. Быстрые победы: (a) зафиксировать алиас `alembic_helpers` в packaging/import policy; (b) добавить guard на dialect в Alembic env; (c) в CI добавить route/openapi dump jobs для всех FastAPI сервисов.

### Главные блокеры (факт)
- Docker недоступен -> невозможно выполнить обязательный full-stack smoke.
- Alembic import-path зависит от внешнего `PYTHONPATH`.
- Alembic env жёстко PostgreSQL-oriented, локальная проверка SQLite невозможна.
- Много mock/stub путей с default-режимами в integration-hub/logistics/document-service.

### Quick wins (low effort)
- Внести нормализованный import в миграции (`from app.alembic_helpers import ...`) или package-level shim.
- Добавить `if connection.dialect.name == "postgresql"` вокруг `CREATE SCHEMA`.
- Включить `scripts/print_alembic_state.py` в CI как обязательный pre-merge check.
- Добавить статическую проверку duplicate OpenAPI operation IDs.

## 2.2 Proof Pack: Run Logs

### Commands executed
1. `python inspect_neft_repo.py --output docs/diag/full_repo_audit_20260224.txt`
2. `python -m compileall platform/processing-core/app platform/auth-host/app platform/ai-services/risk-scorer/app platform/crm-service/app platform/document-service/app platform/integration-hub/neft_integration_hub platform/logistics-service/neft_logistics_service`
3. `docker compose version`
4. `cd platform/processing-core/app && alembic heads`
5. `cd platform/processing-core/app && PYTHONPATH=/workspace/neft-processing/platform/processing-core:/workspace/neft-processing/shared/python DATABASE_URL=sqlite:///./tmp.db alembic heads`
6. `cd platform/processing-core/app && PYTHONPATH=/workspace/neft-processing/platform/processing-core:/workspace/neft-processing/shared/python DATABASE_URL=sqlite:///./tmp.db alembic history --verbose | head -n 80`
7. `cd platform/processing-core/app && PYTHONPATH=/workspace/neft-processing/platform/processing-core:/workspace/neft-processing/shared/python DATABASE_URL=sqlite:///./tmp_alembic_audit.db alembic upgrade head`
8. `PYTHONPATH=/workspace/neft-processing/shared/python:/workspace/neft-processing/platform/integration-hub:/workspace/neft-processing/platform/logistics-service:/workspace/neft-processing/platform/document-service pytest -q platform/integration-hub/neft_integration_hub/tests/test_otp_send.py platform/logistics-service/neft_logistics_service/tests/test_service.py platform/document-service/app/tests/test_sign_service.py`

### Outputs (key evidence)
- Docker: `bash: command not found: docker`.
- Alembic (без PYTHONPATH): `ModuleNotFoundError: No module named 'alembic_helpers'`.
- Alembic (с PYTHONPATH):
  - `20299990_0189_phase3_financial_hardening (head)`
  - `20300120_0205_merge_heads (head)`
- Alembic upgrade on sqlite failed: `sqlite3.OperationalError: near "SCHEMA": syntax error` for `CREATE SCHEMA IF NOT EXISTS processing_core`.
- Targeted tests: `10 passed`.
- Compile/import sanity: `compileall` completed with exit code 0.

### Env/tool availability
- Python: available.
- Pytest: available.
- Alembic: available.
- Docker: unavailable in this environment.

## 2.3 Service Map

| Service | Entrypoint | Routes | OpenAPI | Config keys (observed) | External deps | Status |
|---|---|---:|---|---|---|---|
| processing-core | `platform/processing-core/app/main.py` | 2494 | yes (1743 paths) | `DATABASE_URL`, `APP_ENV`, API prefix vars | Postgres, Redis/Celery, integrations | Partial (static only) |
| auth-host | `platform/auth-host/app/main.py` | 117 | yes (62 paths) | `DATABASE_URL`, JWT/auth settings | Postgres, token/JWKS | Partial (static only) |
| ai risk-scorer | `platform/ai-services/risk-scorer/app/main.py` | 34 | yes (23 paths) | `DATABASE_URL`, model/runtime vars | Postgres, AI provider | Partial |
| billing-clearing | `platform/billing-clearing/app/main.py` | n/a FastAPI | n/a | Celery settings | broker/backend DB | Celery-only entrypoint |
| crm-service | `platform/crm-service/app/main.py` | 34 | yes (18 paths) | `DATABASE_URL` | Postgres | Partial |
| document-service | `platform/document-service/app/main.py` | 12 | yes (7 paths) | `PROVIDER_X_MODE`, provider URL | sign provider (mock/real), storage | Partial |
| integration-hub | `platform/integration-hub/neft_integration_hub/main.py` | 35 | yes (29 paths) | `DIADOK_MODE`, `NOTIFICATIONS_MODE`, `EMAIL_PROVIDER_MODE` | EDO/email/notification providers | Partial |
| logistics-service | `platform/logistics-service/neft_logistics_service/main.py` | 14 | yes (9 paths) | `LOGISTICS_PROVIDER` | OSRM/integration-hub/mock | Partial |

## 2.4 Scenario Matrix (>=30)

> Reachable = route registration + module import chain confirmed statically and/или via OpenAPI dump.

| # | Scenario | Endpoint | Chain (files:lines) | Reachable | Uses stub/mock? | Blocker |
|---:|---|---|---|---|---|---|
| 1 | Auth health | `GET /api/v1/auth/health` | auth-host `app/main.py` -> `api/routes/auth.py:health` | Yes | No | none |
| 2 | Auth login | `POST /api/v1/auth/login` | auth route -> auth service/token issue | Yes | No | DB/runtime deps |
| 3 | Auth register | `POST /api/v1/auth/register` | auth route -> user create | Yes | No | DB required |
| 4 | Auth verify token | `GET /api/v1/auth/verify` | auth route -> token verifier | Yes | No | JWT key consistency |
| 5 | Auth refresh | `POST /api/v1/auth/refresh` | auth route -> refresh token | Yes | No | session store |
| 6 | Auth logout | `POST /api/v1/auth/logout` | auth route -> revoke | Yes | No | DB/session |
| 7 | Auth me | `GET /api/v1/auth/me` | auth route -> principal resolver | Yes | No | claims quality |
| 8 | Admin users list | `GET /api/v1/admin/users` | auth-host admin_users router | Yes | No | RBAC claim correctness |
| 9 | Client create | `POST /api/v1/clients` | processing-core router -> handler -> db session | Yes | No | DB required |
|10 | Client list | `GET /api/v1/clients` | processing-core router -> handler -> query | Yes | No | DB required |
|11 | Prices active | `GET /api/v1/prices/active` | processing-core api routes -> pricing service | Yes | Possible fallback | pricing source |
|12 | Transactions list | `GET /api/v1/transactions` | endpoint module `transactions` -> storage | Yes | No | DB required |
|13 | Operations read | `GET /api/v1/operations` | operations router -> service -> ORM | Yes | No | DB required |
|14 | Reports billing | `GET /api/v1/reports/billing/*` | reports router -> billing services | Yes | No | background jobs |
|15 | Internal pricing resolve | `POST /api/v1/internal/pricing/resolve` | internal route -> rules/pricing service | Yes | No | model data |
|16 | Internal rules evaluate | `POST /api/v1/internal/rules/evaluate` | route -> rules engine | Yes | No | rules config |
|17 | Client portal profile | `/api/client/*` | client portal router -> service | Yes | No | auth guard |
|18 | Partner portal profile | `/api/partner/*` | partner router -> partner service | Yes | No | auth guard |
|19 | Admin runtime health | `/api/admin/runtime/*` | admin_runtime router -> metrics service | Yes | No | none |
|20 | Billing summary | `/api/billing/*` | billing router -> billing metrics/services | Yes | No | DB/jobs |
|21 | Payouts queue | `/api/payouts/*` | payouts endpoint -> payout service | Yes | No | provider integration |
|22 | Refund workflow | `/api/invoices/*refund*` | finance router -> refunds | Yes | No | external provider |
|23 | Clearing batch ops | `/api/clearing/*` | clearing services -> ledger | Yes | No | DB + jobs |
|24 | Client documents v1 | `/api/client/documents/v1/*` | document router -> document service client | Yes | Yes (stub links) | provider mode |
|25 | Admin documents v1 | `/api/admin/documents/v1/*` | admin docs router -> templates/sign flow | Yes | Mock optional | external signer |
|26 | EDO partner dispatch | `/api/partner/edo/*` | partner edo router -> EDO provider | Yes | Yes (stub option) | provider real mode |
|27 | Notifications send | integration-hub `/api/int/v1/notifications/send` | main route -> notifications mode switch | Yes | Yes (default mock) | prod mode config |
|28 | OTP send | integration-hub `/api/int/v1/otp/send` | route -> otp provider | Yes | mock/real switch | external otp |
|29 | Email send | integration-hub `/api/int/notify/email/send` | route -> email provider | Yes | default mock | real SMTP/API |
|30 | Logistics ETA | logistics `/v1/eta` | route -> provider factory -> osrm/integration/mock | Yes | mock fallback | external API |
|31 | Logistics trips create | logistics `/v1/trips/create` | route -> provider -> storage | Yes | mock fallback | external API |
|32 | Logistics fuel consumption | logistics `/v1/fuel/consumption` | route -> provider | Yes | mock fallback | ext deps |
|33 | CRM contacts CRUD | crm `/api/v1/crm/contacts` | router -> crm services -> ORM | Yes | No | DB required |
|34 | CRM deals CRUD | crm `/api/v1/crm/deals` | router -> deal service -> ORM | Yes | No | DB required |
|35 | Document render | doc `/v1/render` | router -> render service -> templates | Yes | No | template assets |
|36 | Document sign | doc `/v1/sign/*` | router -> sign registry -> provider_x | Yes | default mock | real signer cfg |

## 2.5 Stub/Mock/NotImplemented Reachability Map

| Finding | File:line | Class | Importers | Enable path | Fix recommendation |
|---|---|---|---|---|---|
| `NotImplementedError` in EDO base provider methods | `platform/processing-core/app/integrations/edo/provider.py` | D | EDO integrations | abstract base chosen by provider selector | keep abstract + enforce non-base instantiation tests |
| `NotImplementedError` in helpdesk service interface | `platform/processing-core/app/services/helpdesk_service.py` | D | helpdesk adapters | provider binding | add concrete default provider + startup assert |
| mock notifications default | `platform/integration-hub/neft_integration_hub/settings.py` | C | `main.py` notification route | `NOTIFICATIONS_MODE` default=`mock` | change default in prod profile; startup warning |
| mock email default | `platform/integration-hub/neft_integration_hub/settings.py` | C | `main.py` email route | `EMAIL_PROVIDER_MODE` default=`mock` | same as above |
| diadok_mode default mock | `platform/integration-hub/neft_integration_hub/settings.py` | D | EDO send/status | `DIADOK_MODE` | enforce explicit provider in prod |
| provider_x mock mode | `platform/document-service/app/settings.py` | D | sign registry | `PROVIDER_X_MODE` | explicit prod fail-fast on mock |
| logistics provider mock fallback | `platform/logistics-service/neft_logistics_service/settings.py` | D | provider factory | `LOGISTICS_PROVIDER` | prod policy deny mock |
| OSRM provider fallback to mock | `platform/logistics-service/neft_logistics_service/providers/osrm.py` | D | main provider chain | runtime fallback path | metrics + alert when fallback used |
| integration_hub provider fallback mock | `platform/logistics-service/neft_logistics_service/providers/integration_hub_provider.py` | D | provider chain | runtime exception fallback | same |
| events placeholder registry | `platform/processing-core/events/subscribers.py` | A | none runtime-critical | no active binding evidence | remove/implement or exclude from prod tree |
| TODO/FIXME/placeholder in non-runtime docs/events metadata | `platform/processing-core/events/*` | A | none | docs/static | no-op / cleanup |

> Full raw hitlist: `/tmp/stub_hits.txt` (166 matches, including tests).

## 2.6 Alembic & DB State

### State
- `alembic heads` (default env): FAIL (`ModuleNotFoundError: alembic_helpers`).
- `alembic heads` (with fixed `PYTHONPATH`): PASS with 2 heads:
  - `20299990_0189_phase3_financial_hardening`
  - `20300120_0205_merge_heads`
- `alembic history --verbose`: loads and prints graph (sample captured).
- `alembic upgrade head` against sqlite: FAIL (`CREATE SCHEMA` not supported).

### Root-cause for `alembic_helpers`
- Migration files import `from alembic_helpers import ...`.
- Module actually resolved via `platform/processing-core/alembic_helpers.py` -> `app/alembic_helpers.py`.
- Without repo-specific `PYTHONPATH`, CLI cannot find module.

### Minimal fix plan (code, not applied in this audit)
1. Replace imports in migrations to stable path `from app.alembic_helpers import ...`.
2. Or package/install `processing-core` as module before Alembic runs.
3. Add CI check: run `alembic heads` in clean env without ad-hoc `PYTHONPATH`.
4. Add dialect guard in `alembic/env.py` around `CREATE SCHEMA` for non-Postgres local checks.

## 2.7 RBAC Proof

| Role | Token claims | Protected endpoints | Expected status | Evidence |
|---|---|---|---|---|
| admin | `role=admin`, elevated scopes | `/api/v1/admin/users`, admin auth-host routes | 200 for admin, 403 for non-admin | route registration + admin router presence |
| client | `role=client`, tenant/client ids | `/api/client/*`, `/api/client/documents/*` | 200 for own scope, 403 outside scope | client routers included in processing-core |
| partner | `role=partner`, partner/org ids | `/api/partner/*`, `/api/partner/edo/*` | 200 for partner scope, 403 otherwise | partner routers included in processing-core |

Ограничение: runtime curl-подтверждение 200/403 не выполнено из-за отсутствия поднятого docker stack.

## 2.8 Next Actions (PR Plan)

- **PR-1**: Stabilize Alembic imports.
  - Files: `platform/processing-core/app/alembic/versions/*.py` (import lines), possibly `alembic/env.py`.
  - Risk: low-medium (mass touch migration files).
  - Acceptance: `alembic heads` passes without manual `PYTHONPATH`.
  - Verify: `cd platform/processing-core/app && alembic heads`.

- **PR-2**: Dialect-safe Alembic bootstrap.
  - Files: `platform/processing-core/app/alembic/env.py`.
  - Risk: low.
  - Acceptance: sqlite dry-run does not fail on `CREATE SCHEMA`.
  - Verify: `DATABASE_URL=sqlite:///... alembic upgrade head` (or controlled subset).

- **PR-3**: Prod guardrails for mock/stub providers.
  - Files: integration-hub/document-service/logistics settings/startup checks.
  - Risk: medium (config behavior change).
  - Acceptance: app refuses prod boot with mock defaults unless explicit override.
  - Verify: startup tests for prod profile.

- **PR-4**: RBAC contract tests for admin/client/partner critical endpoints.
  - Files: auth-host + processing-core tests.
  - Risk: medium.
  - Acceptance: automated 200/403 matrix in CI.
  - Verify: `pytest -q` security suite.

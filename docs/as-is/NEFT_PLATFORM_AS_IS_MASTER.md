# NEFT Platform — AS-IS Master Documentation

> **Scope:** This document describes what is *actually implemented* in the repository at `/workspace/neft-processing` and how to run/check it. Any missing components are explicitly marked **NOT IMPLEMENTED**. All claims reference concrete files.

## 2.1 Executive Snapshot

**Core/Trust — COMPLETE**
- Core API, auth-host, audit log with hash chain, audit signing backends, WORM protections, and admin/client/partner APIs are implemented in the `processing-core` and `auth-host` services. (See `platform/processing-core/app/main.py`, `platform/processing-core/app/services/audit_service.py`, `platform/processing-core/app/services/audit_signing.py`, `platform/processing-core/app/alembic/versions/0042_audit_log.py`, `platform/auth-host/app/main.py`.)

**Finance — COMPLETE**
- Billing flows, invoices/payments/refunds, internal ledger, posting engine, reconciliation, payouts, accounting exports, and SLA-based billing flows are implemented with idempotency and invariants. (See `platform/processing-core/app/services/finance.py`, `platform/processing-core/app/models/internal_ledger.py`, `platform/processing-core/app/services/ledger/posting_engine.py`, `platform/processing-core/app/services/finance_invariants/checker.py`, `platform/processing-core/app/alembic/versions/20291920_0100_billing_flows_v1.py`.)

**Fuel/Fleet — PARTIAL**
- Fuel cards, limits, ingestion, anomaly detection, notifications, and policies exist; provider framework is present but real providers are stubs/templates only. (See `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/services/fleet_ingestion_service.py`, `platform/processing-core/app/services/fleet_anomaly_service.py`, `platform/processing-core/app/integrations/fuel/providers/stub_provider.py`, `platform/processing-core/app/integrations/fuel/providers/http_provider_template/client.py`.)

**Marketplace — PARTIAL**
- Marketplace catalog, orders, promotions, sponsored offers, analytics, SLA/penalties and booking flows are implemented; moderation workflows are **NOT IMPLEMENTED** (no moderation-specific models/routers found). (See `platform/processing-core/app/models/marketplace_catalog.py`, `platform/processing-core/app/routers/partner/marketplace_catalog.py`, `platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/routers/client_marketplace_orders.py`.)

**Policy/Response — PARTIAL**
- Policy engine for finance/documents and fleet policy engine/escalations exist; unified policy governance UI is partial in client/admin portals. (See `platform/processing-core/app/services/policy/engine.py`, `platform/processing-core/app/services/fleet_policy_engine.py`, `platform/processing-core/app/services/ops/escalations.py`, `frontends/client-portal/src/App.tsx`, `frontends/admin-ui/src/router/index.tsx`.)

**Notifications — PARTIAL**
- Email, Telegram, and Web Push channels implemented via fleet notification dispatcher and outbox; SMS/voice providers are **NOT IMPLEMENTED**. (See `platform/processing-core/app/services/fleet_notification_dispatcher.py`, `platform/processing-core/app/services/notifications/telegram_sender.py`, `platform/processing-core/app/services/notifications/webpush_sender.py`.)

**Analytics UI — PARTIAL**
- Client portal contains analytics pages; BI ingestion and exports are implemented in core API, but no standalone analytics UI service exists. (See `frontends/client-portal/src/App.tsx`, `platform/processing-core/app/services/bi/metrics.py`, `platform/processing-core/app/api/v1/endpoints/bi.py`.)

**Integrations — PARTIAL**
- Fuel provider framework is implemented with stub/template connectors; Integration Hub exists in code but is **NOT IMPLEMENTED** in docker-compose runtime. (See `platform/processing-core/app/integrations/fuel/base.py`, `platform/integration-hub/neft_integration_hub/main.py`, `docker-compose.yml`.)

**Portals — COMPLETE**
- Admin, Client, Partner portals implemented in React; admin/client are included in docker-compose; partner portal exists but container is **NOT IMPLEMENTED** in compose. (See `frontends/admin-ui/src/router/index.tsx`, `frontends/client-portal/src/App.tsx`, `frontends/partner-portal/src/App.tsx`, `docker-compose.yml`.)

**Gateway — COMPLETE**
- Nginx gateway routes API namespaces and SPA paths for admin/client/partner. (See `gateway/nginx.conf`.)

**Observability — PARTIAL**
- Prometheus, Grafana, Jaeger, OTel Collector wired; Loki/log aggregation is **NOT IMPLEMENTED** in compose. (See `infra/prometheus.yml`, `infra/otel-collector-config.yaml`, `docker-compose.yml`.)

---

## 2.2 Repository Map (папки и назначение)

Top-level map (selected):

- `platform/` — backend services and domain modules.
  - `platform/processing-core/` — Core API (billing, fleet, marketplace, audit, etc.). (`platform/processing-core/app/main.py`)
  - `platform/auth-host/` — auth service for JWT issuing/admin bootstrap. (`platform/auth-host/app/main.py`)
  - `platform/ai-services/risk-scorer/` — AI risk scoring stub service. (`platform/ai-services/risk-scorer/app/main.py`)
  - `platform/billing-clearing/` — Celery workers/beat for billing/clearing flows. (`platform/billing-clearing/Dockerfile`)
  - `platform/logistics-service/` — Logistics ETA/deviation service. (`platform/logistics-service/neft_logistics_service/main.py`)
  - `platform/document-service/` — PDF render/sign/verify service. (`platform/document-service/app/main.py`)
  - `platform/crm-service/` — CRM stub service. (`platform/crm-service/app/main.py`)
  - `platform/integration-hub/` — Integration Hub (webhooks + EDO) codebase; not wired in compose. (`platform/integration-hub/neft_integration_hub/main.py`)
- `frontends/` — React SPAs for admin/client/partner portals. (`frontends/admin-ui`, `frontends/client-portal`, `frontends/partner-portal`)
- `gateway/` — Nginx gateway image and routing config. (`gateway/nginx.conf`)
- `infra/` — observability and infra configs (Prometheus, Grafana, OTel). (`infra/prometheus.yml`, `infra/otel-collector-config.yaml`)
- `scripts/` — operational scripts; many Windows `.cmd` entrypoints. (e.g., `scripts/migrate.cmd`, `scripts/smoke_billing_v14.cmd`)
- `docs/` — existing docs; this AS-IS file is under `docs/as-is/`. (`docs/`)
- `docker-compose.yml` — main local stack definitions. (`docker-compose.yml`)
- `db/` — database data/init/backup helper directories. (`db/`)
- `nginx/` — additional nginx config assets outside the gateway image. (`nginx/`)

---

## 2.3 Services Catalog (все сервисы и их ответственность)

> **Source of truth:** `docker-compose.yml`, service code entrypoints.

### Core stack

**gateway (nginx)**
- **Container:** `gateway` (`docker-compose.yml`).
- **Role:** API + SPA routing, request-id propagation. (`gateway/nginx.conf`)
- **Ports:** 80→80.
- **Health:** `GET /health` → `200 OK` text. (`gateway/nginx.conf`)
- **Metrics:** `GET /metrics` returns `gateway_up 1`. (`gateway/nginx.conf`)
- **Dependencies:** core-api, auth-host, ai-service (compose `depends_on`).
- **Routes:** `/api/core/*`, `/api/auth/*`, `/api/ai/*`, `/api/logistics/*`, `/api/docs/*`, SPA paths `/admin/`, `/client/`, `/partner/`. (`gateway/nginx.conf`)

**core-api (processing-core)**
- **Container:** `core-api`. (`docker-compose.yml`)
- **Role:** Core domain API (finance, fuel/fleet, marketplace, CRM, audit, policy). (`platform/processing-core/app/main.py`)
- **Ports:** 8001→8000 (compose), internal 8000.
- **Health:** `GET /api/core/health` or `GET /api/core/api/v1/health` (gateway routed). (`platform/processing-core/app/main.py`, `platform/processing-core/app/api/routes/health.py`, `gateway/nginx.conf`)
- **Metrics:** `GET /metrics` (Prometheus text). (`platform/processing-core/app/main.py`)
- **Key env:** `NEFT_DB_SCHEMA`, `NEFT_S3_*`, `DOCUMENT_SERVICE_ENABLED`, `LOGISTICS_SERVICE_ENABLED`, `NEFT_AUTH_ISSUER/AUDIENCE`, `BI_CLICKHOUSE_ENABLED`, `CLICKHOUSE_URL`. (`docker-compose.yml`, `shared/python/neft_shared/settings.py`)
- **Dependencies:** Postgres, Redis, MinIO; optional ClickHouse/logistics/document service. (`docker-compose.yml`, `shared/python/neft_shared/settings.py`)
- **Ownership:** Tables and migrations in `platform/processing-core/app/models` and `platform/processing-core/app/alembic/versions`.

**auth-host**
- **Container:** `auth-host`. (`docker-compose.yml`)
- **Role:** Authentication, JWT issuance, admin bootstrap, user management. (`platform/auth-host/app/main.py`, `platform/auth-host/app/bootstrap.py`)
- **Ports:** 8002→8000.
- **Health:** `GET /api/auth/health`. (`platform/auth-host/app/api/routes/health.py`, `platform/auth-host/app/main.py`)
- **Metrics:** `GET /api/v1/metrics`. (`platform/auth-host/app/main.py`)
- **Key env:** `NEFT_AUTH_ISSUER`, `NEFT_AUTH_AUDIENCE`, `AUTH_KEY_DIR`, bootstrap envs. (`platform/auth-host/app/settings.py`, `.env.example`)
- **Dependencies:** Postgres, Redis. (`docker-compose.yml`)

**ai-service (risk scorer)**
- **Container:** `ai-service`. (`docker-compose.yml`)
- **Role:** Risk scoring API endpoints. (`platform/ai-services/risk-scorer/app/main.py`)
- **Ports:** 8003→8000.
- **Health:** `GET /api/ai/api/v1/health` via gateway or `/api/v1/health` direct. (`platform/ai-services/risk-scorer/app/api/v1/health.py`, `gateway/nginx.conf`)
- **Metrics:** `GET /metrics` (simple). (`platform/ai-services/risk-scorer/app/main.py`)
- **Key env:** `LOG_LEVEL`, `AI_MODEL_NAME`. (`platform/ai-services/risk-scorer/app/settings.py`)
- **Dependencies:** Redis (compose). (`docker-compose.yml`)

**workers / beat / flower**
- **Containers:** `workers`, `beat`, `flower`. (`docker-compose.yml`)
- **Role:** Celery workers and scheduler for billing/clearing/pdf jobs; Flower UI for monitoring. (`platform/billing-clearing/Dockerfile`, `services/flower/Dockerfile`)
- **Ports:** Flower 5555→5555.
- **Health:** workers/beat via Celery ping; Flower API check. (`docker-compose.yml`)
- **Key env:** `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `NEFT_S3_*`, `BI_CLICKHOUSE_ENABLED`. (`docker-compose.yml`, `.env.example`)

**celery-exporter**
- **Container:** `celery-exporter`. (`docker-compose.yml`)
- **Role:** Prometheus metrics for Celery. (`docker-compose.yml`)
- **Ports:** 9808 (internal). Metrics `GET /metrics`. (`docker-compose.yml`)

### Supporting services

**postgres**
- **Role:** Primary database. (`docker-compose.yml`)
- **Port:** 5432.

**redis**
- **Role:** Cache + Celery broker/backend. (`docker-compose.yml`)
- **Port:** 6379.

**minio / minio-init / minio-health**
- **Role:** Object storage for invoices, exports, documents, audit exports. (`docker-compose.yml`, `infra/minio-init.sh`)
- **Ports:** 9000 (S3), 9001 (console).

**clickhouse**
- **Role:** Optional BI storage. (`docker-compose.yml`, `shared/python/neft_shared/settings.py`)
- **Ports:** 8123, 9000→9002.

### Peripheral services

**logistics-service**
- **Role:** ETA/deviation calculations, explainable results. (`platform/logistics-service/neft_logistics_service/main.py`)
- **Health:** `/health`; **metrics** `/metrics`. (`platform/logistics-service/neft_logistics_service/main.py`)
- **Note:** Used when `LOGISTICS_SERVICE_ENABLED=1`. (`shared/python/neft_shared/settings.py`)

**document-service**
- **Role:** Render HTML→PDF, sign/verify documents, presign storage. (`platform/document-service/app/main.py`)
- **Health:** `/health`; **metrics** `/metrics`. (`platform/document-service/app/main.py`)

**crm-service**
- **Role:** Stub service with health/metrics only. (`platform/crm-service/app/main.py`)

### Observability stack

**otel-collector / jaeger / prometheus / grafana**
- Config and routing in `infra/otel-collector-config.yaml` and `infra/prometheus.yml`. (`infra/otel-collector-config.yaml`, `infra/prometheus.yml`, `docker-compose.yml`)
- Loki/log aggregation is **NOT IMPLEMENTED** in compose. (`docker-compose.yml`)

### NOT IMPLEMENTED in compose
- **partner-web** container is referenced in gateway but not defined in compose. (`gateway/nginx.conf`, `docker-compose.yml`)
- **integration-hub** code exists but not wired as a container. (`platform/integration-hub/neft_integration_hub/main.py`, `docker-compose.yml`)

---

## 2.4 API Map (основные endpoints)

> **Base paths:**
> - Gateway: `/api/core/*`, `/api/auth/*`, `/api/ai/*` (`gateway/nginx.conf`)
> - Core API also serves `/api/v1/*` directly when called without gateway. (`platform/processing-core/app/main.py`)

### Core / Trust
- **Health & metrics:** `/api/core/health`, `/api/core/api/v1/health`, `/metrics`. (`platform/processing-core/app/api/routes/health.py`, `platform/processing-core/app/main.py`)
- **Auth glue:** `/api/core/api/v1/auth/*` (proxy via auth-host). (`platform/processing-core/app/api/routes/auth.py`)
- **Error format:** JSON error envelope `{error:{type,message}, meta:{correlation_id,path}}`. (`platform/processing-core/app/error_handlers.py`)

### Finance
- **Billing/Invoices/Payments/Refunds:** `/api/v1` billing endpoints and admin router `/api/v1/admin/billing/*`. (`platform/processing-core/app/api/v1/endpoints/billing_invoices.py`, `platform/processing-core/app/routers/admin/billing.py`)
- **Ledger/Accounts:** `/api/v1/admin/ledger`, `/api/v1/admin/accounts`. (`platform/processing-core/app/routers/admin/ledger.py`, `platform/processing-core/app/routers/admin/accounts.py`)
- **Clearing/Payouts/Settlement:** `/api/v1/admin/clearing`, `/api/v1/admin/settlement*`, `/api/v1/payouts`. (`platform/processing-core/app/routers/admin/clearing.py`, `platform/processing-core/app/routers/admin/settlement_v1.py`, `platform/processing-core/app/api/v1/endpoints/payouts.py`)

### Fuel / Fleet
- **Client fleet API:** `/api/client/fleet/*` (cards, groups, employees, limits, notifications). (`platform/processing-core/app/routers/client_fleet.py`)
- **Fleet ingestion (internal):** `/api/internal/fleet/*`. (`platform/processing-core/app/routers/internal/fleet.py`)
- **Client portal shortcuts:** `/client/api/v1/*`. (`platform/processing-core/app/routers/client.py`, `platform/processing-core/app/routers/client_vehicles.py`)

### Marketplace
- **Client marketplace:** `/client/marketplace/*`, `/client/marketplace/orders/*`, `/client/marketplace/deals/*`. (`platform/processing-core/app/routers/client_marketplace.py`, `platform/processing-core/app/routers/client_marketplace_orders.py`, `platform/processing-core/app/routers/client_marketplace_deals.py`)
- **Partner marketplace:** `/partner/*` (catalog, orders, promotions, analytics, coupons, sponsored). (`platform/processing-core/app/routers/partner/marketplace_catalog.py`, `platform/processing-core/app/routers/partner/marketplace_orders.py`, `platform/processing-core/app/routers/partner/marketplace_promotions.py`, `platform/processing-core/app/routers/partner/marketplace_analytics.py`)

### Policy / Response
- **Cases:** `/api/core/cases` + admin cases. (`platform/processing-core/app/routers/cases.py`, `platform/processing-core/app/routers/admin/cases.py`)
- **Ops escalations:** `/api/v1/admin/ops/*`. (`platform/processing-core/app/routers/admin/ops.py`)

### Notifications
- **Fleet notifications:** `/api/client/fleet/notifications/*`. (`platform/processing-core/app/routers/client_fleet.py`)
- **Telegram webhook:** `/api/internal/telegram/webhook` (path configurable). (`platform/processing-core/app/routers/internal/telegram.py`, `shared/python/neft_shared/settings.py`)

### Integrations
- **Logistics service:** `/api/v1/logistics/*` (core) and `/api/logistics/*` (gateway). (`platform/processing-core/app/api/v1/endpoints/logistics.py`, `gateway/nginx.conf`)
- **EDO intake:** `/api/v1/edo/*`. (`platform/processing-core/app/api/v1/endpoints/edo_events.py`)

### Example request/response
- **KPI:** `GET /api/core/kpi/summary?window_days=7` → KPI summary JSON. (`platform/processing-core/app/routers/kpi.py`, example in `README.md`)
- **Errors:** `422` validation error returns `{error:{type:"validation_error",...}}`. (`platform/processing-core/app/error_handlers.py`)

**Idempotency**
- Many write endpoints accept `idempotency_key` in request body/query; enforced via DB unique constraints. (Examples: `platform/processing-core/app/api/v1/endpoints/billing_invoices.py`, `platform/processing-core/app/models/billing_flow.py`, `platform/processing-core/app/models/internal_ledger.py`.)

---

## 2.5 Data Model Map (таблицы/миграции)

> **Source:** SQLAlchemy models in `platform/processing-core/app/models` and Alembic migrations in `platform/processing-core/app/alembic/versions`.

### Core/Audit/Trust
- `audit_log` + immutable trigger + hash chain. (`platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/alembic/versions/0042_audit_log.py`)
- Audit signing keys registry: `audit_signing_keys`. (`platform/processing-core/app/models/audit_signing_keys.py`, `platform/processing-core/app/alembic/versions/20250320_0106_audit_signing_keys_object_lock.py`)
- WORM retention tables: `audit_legal_holds`, `audit_purge_log`. (`platform/processing-core/app/models/audit_retention.py`, `platform/processing-core/app/alembic/versions/20291780_0095_audit_retention_worm.py`)

### Finance/Ledger
- Double-entry ledger: `internal_ledger_accounts`, `internal_ledger_transactions`, `internal_ledger_entries`. (`platform/processing-core/app/models/internal_ledger.py`, `platform/processing-core/app/alembic/versions/20291201_0056_internal_ledger_v1.py`)
- Billing flows: `billing_invoices`, `billing_payments`, `billing_refunds`. (`platform/processing-core/app/models/billing_flow.py`, `platform/processing-core/app/alembic/versions/20291920_0100_billing_flows_v1.py`)
- Billing periods/summary/job runs: `billing_periods`, `billing_summary`, `billing_job_runs`. (`platform/processing-core/app/models/billing_period.py`, `platform/processing-core/app/models/billing_summary.py`, `platform/processing-core/app/models/billing_job_run.py`)
- Payouts/settlement: `payout_batches`, `settlement_*`. (`platform/processing-core/app/models/payout_batch.py`, `platform/processing-core/app/models/settlement_v1.py`)
- Reconciliation: `reconciliation_runs`, `reconciliation_discrepancies`. (`platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/alembic/versions/20291910_0099_reconciliation_v1.py`)

### Fuel/Fleet
- `fuel_cards`, `fuel_transactions`, `fuel_limits`, `fuel_card_groups`, `fuel_group_access`, `fleet_notification_outbox`. (`platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/alembic/versions/20250220_0103_fuel_fleet_v1.py`, `platform/processing-core/app/alembic/versions/20291960_0104_fleet_notifications_v2.py`)
- Ingestion jobs: `fuel_ingest_jobs`. (`platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/alembic/versions/20260201_0104_fleet_ingestion_v1.py`)

### Marketplace
- Catalog/orders/promotions: `marketplace_products`, `marketplace_orders`, `marketplace_order_events`, `marketplace_promotions`. (`platform/processing-core/app/models/marketplace_catalog.py`, `platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/models/marketplace_promotions.py`)
- SLA & penalties: `marketplace_order_sla`, `marketplace_sla_notification_outbox`. (`platform/processing-core/app/models/marketplace_order_sla.py`, `platform/processing-core/app/alembic/versions/20292010_0108_marketplace_order_sla_v1.py`)
- Contracts/sponsored: `marketplace_contracts`, `sponsored_spend_ledger`. (`platform/processing-core/app/models/marketplace_contracts.py`, `platform/processing-core/app/models/marketplace_sponsored.py`)

### Policy/Response
- Cases/escalations: `cases`, `case_events`, `ops_escalations`. (`platform/processing-core/app/models/cases.py`, `platform/processing-core/app/models/ops.py`, `platform/processing-core/app/alembic/versions/20291720_0089_cases_v1.py`, `platform/processing-core/app/alembic/versions/20291530_0075_ops_escalations.py`)
- Risk policies/rules: `risk_policy`, `risk_rule`, `risk_threshold*`. (`platform/processing-core/app/models/risk_policy.py`, `platform/processing-core/app/models/risk_rule.py`)

### CRM / Subscriptions
- CRM core, contracts, feature flags, subscriptions: `crm_*`, `subscriptions_*`. (`platform/processing-core/app/models/crm.py`, `platform/processing-core/app/models/subscriptions_v1.py`)

### Documents / Legal
- Documents registry, signatures, legal graph: `documents`, `document_signatures`, `legal_graph_*`. (`platform/processing-core/app/models/documents.py`, `platform/processing-core/app/models/legal_graph.py`)

### Append-only / WORM tables (examples)
- `audit_log`, `case_events`, `decision_memory`, `internal_ledger_entries`, `billing_invoices/payments/refunds`, `marketplace_order_events`, `fuel_transactions` are protected with immutability triggers. (See migrations: `platform/processing-core/app/alembic/versions/0042_audit_log.py`, `20291780_0095_audit_retention_worm.py`, `20291820_0098_internal_ledger_extension_cycle1.py`, `20291920_0100_billing_flows_v1.py`, `20292010_0108_marketplace_orders_v1.py`, `20250220_0103_fuel_fleet_v1.py`.)

---

## 2.6 Trust Layer (подробно)

**Audit chain (hash chain)**
- Each audit log record includes a hash computed from canonical payload + previous hash (GENESIS for first). (`platform/processing-core/app/services/audit_service.py`)
- Audit log is immutable via DB trigger `audit_log_immutable`. (`platform/processing-core/app/alembic/versions/0042_audit_log.py`)

**Signing backends**
- Local signer, AWS KMS signer, and Vault Transit signer implemented. (`platform/processing-core/app/services/audit_signing.py`)
- Configured via `AUDIT_SIGNING_MODE` and related env vars (AWS/Vault settings). (`shared/python/neft_shared/settings.py`, `.env.example`)

**Key registry + rotation readiness**
- Audit signing keys stored in `audit_signing_keys` table; listing endpoint available under admin audit. (`platform/processing-core/app/models/audit_signing_keys.py`, `platform/processing-core/app/routers/admin/audit.py`)

**Redaction (PII safe)**
- Audit payload masking and truncation performed by `audit_service` (`SENSITIVE_KEYS`, payload size limit). (`platform/processing-core/app/services/audit_service.py`)

**WORM: DB triggers + S3 object lock**
- WORM guards in migrations enforce immutability. (Examples: `platform/processing-core/app/alembic/versions/20291780_0095_audit_retention_worm.py`)
- Object lock configuration is driven by `S3_OBJECT_LOCK_*` env vars. (`shared/python/neft_shared/settings.py`, `.env.example`)

**Export verification: hash + signature**
- Case export verification combines hash chain + signature verification. (`platform/processing-core/app/services/case_export_verification_service.py`)

**CI trust gates**
- No dedicated CI trust gate config found in repo (**NOT IMPLEMENTED**). (No files in `.github/workflows` referencing audit signing gates.)

**Manual verification**
- Use audit verification services (`case_export_verification_service`) and admin endpoints for audit keys. (`platform/processing-core/app/services/case_export_verification_service.py`, `platform/processing-core/app/routers/admin/audit.py`)

---

## 2.7 Finance Layer (подробно)

**Internal ledger & invariants**
- Double-entry enforcement + invariants check via `finance_invariants` + posting engine. (`platform/processing-core/app/services/finance_invariants/checker.py`, `platform/processing-core/app/services/ledger/posting_engine.py`)

**Billing flows**
- Invoices, payments, refunds stored in `billing_*` tables; idempotency enforced. (`platform/processing-core/app/models/billing_flow.py`, `platform/processing-core/app/alembic/versions/20291920_0100_billing_flows_v1.py`)

**Reconciliation & settlement**
- Reconciliation runs/discrepancies tables and admin endpoints. (`platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/routers/admin/reconciliation.py`)
- Settlement v1 & payouts through `settlement_v1` and payout models. (`platform/processing-core/app/models/settlement_v1.py`, `platform/processing-core/app/models/payout_batch.py`)

**State machines**
- Billing/invoice transitions in billing services and invariants. (`platform/processing-core/app/services/billing_service.py`, `platform/processing-core/app/services/finance.py`)

**Admin UI coverage**
- Admin portal exposes billing, clearing, payouts, accounts/ledger, operations. (`frontends/admin-ui/src/router/index.tsx`)

**Metrics/alerts/runbooks**
- Metrics emitted from core `/metrics` include billing, payout, reconciliation gauges. (`platform/processing-core/app/main.py`)
- Runbooks exist in `docs/runbooks` but no finance-specific runbook index binding (**PARTIAL**). (`docs/runbooks/`)

---

## 2.8 Fuel Cards / Fleet (подробно)

**Entities**
- Cards, groups, employees, limits, transactions are modeled in `fuel.py`. (`platform/processing-core/app/models/fuel.py`)

**Limits revision-based**
- Limits changes tracked with WORM protection (fuel limits) and audit events. (`platform/processing-core/app/alembic/versions/20250220_0103_fuel_fleet_v1.py`, `platform/processing-core/app/services/fleet_service.py`)

**Transactions append-only**
- `fuel_transactions` is WORM-protected. (`platform/processing-core/app/alembic/versions/20250220_0103_fuel_fleet_v1.py`)

**Ingestion pipeline**
- Ingestion jobs with idempotency, provider/network normalization, dedupe, anomaly detection, policy evaluation. (`platform/processing-core/app/services/fleet_ingestion_service.py`)

**Provider framework**
- Provider interface and registry in `integrations/fuel`. Stub/template providers only. (`platform/processing-core/app/integrations/fuel/base.py`, `platform/processing-core/app/integrations/fuel/providers/stub_provider.py`, `platform/processing-core/app/integrations/fuel/providers/http_provider_template/client.py`)

**Anomaly detection & auto-block**
- Anomaly detection service + policy actions include auto-block. (`platform/processing-core/app/services/fleet_anomaly_service.py`, `platform/processing-core/app/services/fleet_policy_engine.py`)

**Escalation workflows + cases**
- Policy actions can create cases/escalations. (`platform/processing-core/app/services/fleet_policy_engine.py`, `platform/processing-core/app/services/ops/escalations.py`)

**Notifications**
- Outbox with dedupe/retry, channels: email/telegram/webpush. (`platform/processing-core/app/services/fleet_notification_dispatcher.py`, `platform/processing-core/app/models/fuel.py`)

**UX/портал клиента**
- Fleet policies/notifications pages in client portal routes. (`frontends/client-portal/src/App.tsx`)

---

## 2.9 Marketplace (подробно)

**M1..M5 functionality (as implemented)**
- Partner profile/catalog, client browse, orders lifecycle, SLA coupling all present. (See `platform/processing-core/app/routers/partner/marketplace_catalog.py`, `platform/processing-core/app/routers/client_marketplace.py`, `platform/processing-core/app/routers/client_marketplace_orders.py`, `platform/processing-core/app/services/order_sla_consequence_service.py`.)

**Orders state machine + append-only events**
- Orders and order events are modeled, WORM protected. (`platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/alembic/versions/20292010_0108_marketplace_orders_v1.py`)

**Partner portal functions**
- Partner portal routes include products, orders, payouts, integrations. (`frontends/partner-portal/src/App.tsx`)

**Client portal functions**
- Marketplace browsing and orders in client portal. (`frontends/client-portal/src/App.tsx`)

**SLA → billing → settlement**
- SLA consequences flow to billing/ledger. (`platform/processing-core/app/services/order_sla_consequence_service.py`, `platform/processing-core/app/services/settlement_service.py`)

**Moderation**
- **NOT IMPLEMENTED** (no moderation models/routers found).

---

## 2.10 Policy & Response (подробно)

**Unified Policy Center**
- Policy engine implemented for finance/document operations; fleet policy engine for anomalies/breaches. (`platform/processing-core/app/services/policy/engine.py`, `platform/processing-core/app/services/fleet_policy_engine.py`)

**Action/notification policies & executions**
- Action policies + notification policies stored and evaluated for fleet. (`platform/processing-core/app/services/fleet_service.py`, `platform/processing-core/app/services/fleet_policy_engine.py`)

**Explainable rules**
- Explain v2 routes + unified explain services. (`platform/processing-core/app/routers/explain_v2.py`, `platform/processing-core/app/services/explain/unified.py`)

**RBAC**
- Permission guard and role mapping. (`platform/processing-core/app/security/rbac/guard.py`, `platform/processing-core/app/security/rbac/roles.py`)

**Escalation cases UX**
- Admin portal includes cases & ops escalations routes. (`frontends/admin-ui/src/router/index.tsx`)

---

## 2.11 Notifications (подробно)

**Channels/providers**
- Email (SMTP or console), Telegram, Web Push. (`platform/processing-core/app/services/notifications/email_sender.py`, `platform/processing-core/app/services/notifications/telegram_sender.py`, `platform/processing-core/app/services/notifications/webpush_sender.py`)

**Event schemas**
- Fleet notification payloads include `summary`, `route`, `body`, and event type. (`platform/processing-core/app/services/fleet_notification_dispatcher.py`)

**Outbox, retries, dedupe**
- `fleet_notification_outbox` table with retry scheduling, dedupe keys per channel. (`platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/services/fleet_notification_dispatcher.py`)

**Security**
- Webhook HMAC/replay protection is **NOT IMPLEMENTED** in core notifications (no HMAC handler found). (No matches in `platform/processing-core/app/services/notifications`.)

**Runbooks**
- General runbooks exist under `docs/runbooks`. (`docs/runbooks/`)

---

## 2.12 Observability & Ops

**Prometheus metrics + dashboards**
- Prometheus scrapes gateway, core, auth, ai, logistics, document, crm, celery exporter. (`infra/prometheus.yml`)
- Grafana dashboards provisioned in `infra/grafana/dashboards`. (`infra/grafana/dashboards`)

**Loki/Logs**
- **NOT IMPLEMENTED** in compose. (`docker-compose.yml`)

**Tracing (OTel/Jaeger)**
- OTel Collector receives OTLP gRPC on 4317 and exports to Jaeger. (`infra/otel-collector-config.yaml`, `docker-compose.yml`)

**Runbooks index**
- General runbooks are in `docs/runbooks` and `docs/ops`. (`docs/runbooks/`, `docs/ops/`)

**Windows CMD commands (ops)**
- Stack up: `docker compose up -d --build` (also in `README.md`).
- Migrations: `scripts\migrate.cmd`. (`scripts/migrate.cmd`)
- Seeds/demo: `scripts\smoke_billing_v14.cmd` or `scripts\smoke_billing_finance.cmd`. (`scripts/smoke_billing_v14.cmd`, `scripts/smoke_billing_finance.cmd`)
- Diagnostics: `scripts\diag-db.cmd`, `scripts\check_migrations.cmd`. (`scripts/diag-db.cmd`, `scripts/check_migrations.cmd`)

---

## 2.13 Deployment/Env/Config

**docker-compose**
- Local stack defined in `docker-compose.yml` (core services + observability). (`docker-compose.yml`)

**Important env variables**
- Base env list in `.env.example`; shared settings in `shared/python/neft_shared/settings.py`. (`.env.example`, `shared/python/neft_shared/settings.py`)
- Auth bootstrap envs in `platform/auth-host/app/settings.py`. (`platform/auth-host/app/settings.py`)

**Secrets**
- JWT and signing keys are read from env or generated under `auth-keys` volume. (`platform/auth-host/app/settings.py`, `docker-compose.yml`)

---

## 2.14 Terminals / Partners / Integrations

**Terminal support**
- Terminal/merchant/card APIs exist under `/api/v1` routes. (`platform/processing-core/app/api/routes/terminals.py`, `platform/processing-core/app/api/routes/merchants.py`, `platform/processing-core/app/api/routes/cards.py`)

**Provider interface**
- Fuel provider protocol with `health`, `list_cards`, `fetch_transactions`, `fetch_statements`, `map_*`. (`platform/processing-core/app/integrations/fuel/base.py`)

**Polling/backfill/replay**
- Fleet ingestion jobs support idempotent ingestion and dedupe; replay is exposed in admin for notification outbox. (`platform/processing-core/app/services/fleet_ingestion_service.py`, `platform/processing-core/app/routers/admin/fleet_notifications.py`)

**Webhook API contracts**
- Integration Hub (webhooks/EDO) exists in code but not wired to runtime. (`platform/integration-hub/neft_integration_hub/main.py`, `docker-compose.yml`)

**Exports**
- Accounting export batches with S3 delivery; ERP reconciliation models exist. (`platform/processing-core/app/models/accounting_export_batch.py`, `platform/processing-core/app/models/erp_exports.py`)
- 1C/bank export specifics are **NOT IMPLEMENTED** (no 1C-specific code found).

---

## 2.15 Feature Flags / Options (крайние опции)

Подробная матрица флагов: [Feature Flags Matrix](../product/feature_flags_matrix.md).

| Feature flag / option | Default | Where configured | Effect |
| --- | --- | --- | --- |
| `FEATURE_FLAGS` | `ai_scorer:on,ai_anomaly:off` | `.env.example` | Frontend/global feature flag string (parsed by UI/clients). |
| `AI_RISK_ENABLED` | true | `shared/python/neft_shared/settings.py` | Enable AI risk scoring integration. |
| `LOGISTICS_NAVIGATOR_ENABLED` | true | `shared/python/neft_shared/settings.py` | Enables logistics navigator features. |
| `LOGISTICS_SERVICE_ENABLED` | false | `shared/python/neft_shared/settings.py` | Enables calls to logistics-service. |
| `DOCUMENT_SERVICE_ENABLED` | false | `shared/python/neft_shared/settings.py` | Enables document-service integration. |
| `BI_CLICKHOUSE_ENABLED` | false | `shared/python/neft_shared/settings.py` | Enables ClickHouse BI sync. |
| `S3_OBJECT_LOCK_ENABLED` | false | `shared/python/neft_shared/settings.py` | Enables object lock/WORM on S3 exports. |
| CRM feature flags (e.g., `SUBSCRIPTION_METER_FUEL_ENABLED`) | none | `crm_feature_flags` table | Feature gating by client/tenant. (`platform/processing-core/app/models/crm.py`, `platform/processing-core/app/alembic/versions/20291430_0073_crm_feature_flag_subscription_meter_fuel.py`) |

---

## 2.16 Known Issues / Technical Debt (фактическое)

1) **Integration Hub not deployed**
- Evidence: Integration Hub code exists but no compose service. (`platform/integration-hub/neft_integration_hub/main.py`, `docker-compose.yml`)
- **Status:** OPEN
- **Workaround:** Run it manually if needed; otherwise webhooks/EDO in hub are unavailable.
- **Pilot risk:** Webhook/EDO flows not runnable by default.

2) **Loki/log aggregation absent**
- Evidence: No Loki services in compose. (`docker-compose.yml`)
- **Status:** OPEN
- **Workaround:** Use container logs or extend observability stack.
- **Pilot risk:** Limited centralized log search.

---

# How to verify AS-IS

> **All commands are Windows CMD compatible.**

## 1) Поднять стек
```bat
docker compose up -d --build
```

## 2) Проверить health
```bat
curl -f http://localhost/health
curl -f http://localhost/api/core/health
curl -f http://localhost/api/auth/health
curl -f http://localhost/api/ai/api/v1/health
```
(Health endpoints are routed by `gateway/nginx.conf` and implemented in `platform/processing-core/app/api/routes/health.py`, `platform/auth-host/app/api/routes/health.py`, `platform/ai-services/risk-scorer/app/api/v1/health.py`.)

## 3) Проверить metrics
```bat
curl -f http://localhost/metrics
curl -f http://localhost/api/auth/api/v1/metrics
```
(Core metrics at `platform/processing-core/app/main.py`; auth metrics at `platform/auth-host/app/main.py`.)

## 4) Зайти в порталы
- Admin portal: `http://localhost/admin/` (routes in `gateway/nginx.conf`, UI in `frontends/admin-ui`).
- Client portal: `http://localhost/client/` (routes in `gateway/nginx.conf`, UI in `frontends/client-portal`).
- Partner portal: **NOT IMPLEMENTED** in compose; code exists in `frontends/partner-portal`.

## 5) Минимальные smoketests
```bat
pytest -q tests\test_no_merge_markers.py tests\test_smoke_gateway_routing.py
```
(See `README.md` for suggested smoke tests and `tests/` for scripts.)

## 6) Проверить gateway routing /client/* refresh
- Open `http://localhost/client/` and refresh; gateway SPA fallback should serve `client/index.html`. (`gateway/nginx.conf`)

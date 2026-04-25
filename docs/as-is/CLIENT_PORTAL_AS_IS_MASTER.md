# Client Portal — AS-IS Master Snapshot (code-backed)

> Scope rule: only what exists in code. If something is not found in the repo, it is marked **NOT IMPLEMENTED**.

## 3.1 Executive Status (current snapshot)

**Current stage (by implemented scope):** **v1.4** (v1.0–v1.4 feature set largely present; v1.5–v1.6 partially implemented).

**Production-grade now (as implemented in code):**
- Client SPA routing via `/client/` + gateway routing & auth separation with `/api/core/client/*` guarded by client auth, and `/api/core/v1/admin/*` guarded by admin auth. (Gateway + auth host portal separation.)
- Core API health, metrics, and basic observability primitives exist.

**Feature-complete now (as implemented):**
- Client portal dashboard, cards/limits/access (incl. bulk), users/invite/roles, documents list/download, audit viewer/export, support tickets with comments/attachments + SLA, report exports/jobs (async, XLSX, ETA), schedules, notifications.

**Commercial-ready now (as implemented):**
- Subscription plans + entitlements snapshot, billing plan/usage endpoints, invoice generation + PDFs, payment intake (submit + approve/reject), dunning/suspend flow, reconciliation workflows (imports + manual resolve/ignore), contract packs, revenue admin endpoints.

**Evidence (files/endpoints)**:
- `gateway/nginx.conf` (portal routing + auth separation).
- `platform/processing-core/app/routers/client_portal_v1.py` (dashboard, support, exports, invoices, users, cards).
- `platform/processing-core/app/routers/client_me.py` + `platform/processing-core/app/services/entitlements_v2_service.py` (entitlements snapshot).
- `platform/processing-core/app/celery_client.py` + `platform/processing-core/app/tasks/billing_pdf.py` (billing schedules/PDF).
- `platform/processing-core/app/routers/admin/revenue.py` + `platform/processing-core/app/routers/admin/contract_packs.py` (commercial admin).

**How to verify (Windows CMD)**:
- `curl -i http://localhost/client/`
- `curl -i http://localhost/api/core/health`
- `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/dashboard`

## 3.2 Portal Boundaries

**Issuer/audience separation (client vs admin)**
- Auth host issues tokens by `portal` with different issuer/audience (client vs admin). (`/api/auth/v1/auth/login` handles portal selection.)

**Gateway rules (client vs admin, SPA split)**
- `/client/` routes to client SPA; `/admin/` routes to admin SPA. Assets are separated by prefix.
- `/api/core/client/*` requires client auth verification; exception: `/api/core/client/v1/onboarding/*` and `/api/core/client/docflow/*` use short-lived onboarding tokens and are verified inside `processing-core`.
- `/api/core/v1/admin/*` requires admin auth verification.

**Forbidden cross-portal access**
- Enforced by gateway `auth_request` + 401/403 handlers on the protected `/api/core/client/*` and `/api/core/v1/admin/*` prefixes; onboarding-token docflow routes are explicit gateway pass-throughs and remain protected by core's onboarding-token guard.

**Evidence (files/endpoints)**:
- `gateway/nginx.conf` (SPA routing + auth_request guards).
- `platform/auth-host/app/api/routes/auth.py` (portal token config).

**How to verify (Windows CMD)**:
- `curl -i http://localhost/client/`
- `curl -i http://localhost/admin/`
- `curl -i http://localhost/api/core/client/me`

## 3.3 IAM / Entitlements / Billing Enforcement

**`/portal/me` as SSoT (client bootstrap)**
- Portal bootstrap uses `GET /api/core/portal/me` to resolve user, org, roles, subscription and entitlements snapshot (hash + computed_at), then client-specific endpoints enrich the portal state. `GET /api/core/client/me` remains as a compatibility client-focused view built on top of the same portal payload.
- `org.org_type` from `portal/me` is now the shell-composition input for `INDIVIDUAL` vs `BUSINESS`; client UI must not invent a second client-kind source.

**Entitlements engine v2 (snapshot + hash + overrides + addons)**
- `get_org_entitlements_snapshot()` builds snapshot from `org_subscriptions`, `subscription_plan_features`, `subscription_plan_modules`, addons, overrides, and persists `org_entitlements_snapshot` with a hash/version.
- Addons are mapped to feature keys and can override `availability` to ENABLED; overrides can replace feature availability/limits.

**Billing enforcement (soft/hard blocks + where applied)**
- `billing_policy_allow()` implements soft/hard block behavior for OVERDUE and SUSPENDED states; `enforce_entitlement()` raises 403 with structured payload.
- Applied in the client portal for portal writes and export access; also used in fleet client APIs to guard write actions.

**Evidence (files/endpoints)**:
- `platform/processing-core/app/routers/client_me.py` (`/client/me` response with entitlements snapshot).
- `platform/processing-core/app/services/entitlements_v2_service.py` (snapshot/hash/addons/overrides).
- `platform/processing-core/app/services/billing_access.py` (soft/hard block policy + enforcement).
- `platform/processing-core/app/routers/client_portal_v1.py` + `platform/processing-core/app/routers/client_fleet.py` (enforcement call sites).

**How to verify (Windows CMD)**:
- `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/me`
- `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/entitlements`

## 3.4 Onboarding (AS-IS)

**Org create → contract generate → sign → ACTIVE/PENDING**
- Canonical authenticated onboarding flow is frontend `/onboarding*` plus backend `/api/core/client/onboarding/*`; legacy `/connect*` frontend routes are compatibility redirects only.
- Self-signup onboarding flow (`/api/core/client/onboarding/*`) supports status, profile save, contract generation, contract retrieval, and contract signing.
- Contract-sign family is the canonical current authenticated onboarding activation path. On sign: client/onboarding status becomes `ACTIVE` if feature flag `auto_activate_after_sign` enabled, otherwise `PENDING_ACTIVATION`.

**Wizard routes + backend endpoints**
- Frontend canonical routes: `/onboarding`, `/onboarding/plan`, `/onboarding/contract`
- Frontend compatibility redirects: `/connect*` → `/onboarding*`
- Backend canonical onboarding routes:
  - `/api/core/client/onboarding/status`
  - `/api/core/client/onboarding/profile`
  - `/api/core/client/onboarding/contract/generate`
  - `/api/core/client/onboarding/contract`
  - `/api/core/client/onboarding/contract/sign`
- Commercial-layer compatibility state endpoints: `/api/client/onboarding/state` + `/api/client/onboarding/step`
- Client portal org + contract endpoints: `/api/core/client/org`, `/api/core/client/contracts/generate`, `/api/core/client/contracts/current`, `/api/core/client/contracts/sign-simple`

**Status machine**
- `ClientOnboarding` transitions profile → contract → activation; contract sign sets onboarding `ACTIVATION` and client status (`ACTIVE` or `PENDING_ACTIVATION`).
- `POST /api/core/client/onboarding/activate` remains a compatibility/internal route and is not the canonical consumer-facing activation step for the current authenticated onboarding flow.

**Evidence (files/endpoints)**:
- `platform/processing-core/app/routers/client_onboarding.py` (status/profile/contract/generate/sign).
- `platform/processing-core/app/routers/client_portal_v1.py` (org + contract endpoints).
- `platform/processing-core/app/routers/commercial_layer.py` (onboarding state endpoints).

**How to verify (Windows CMD)**:
- `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/onboarding/status`
- `curl -i -X POST -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/onboarding/contract/generate`

## 3.5 Core Modules (AS-IS)

> For each module: Routes, API, RBAC, ABAC, Gating, Evidence, How to verify.

### Users / Membership / Roles
- **Routes/API**: `/client/users`, `/client/users/invite`, `/client/users/{user_id}`, `/client/users/{user_id}/roles`.
- **RBAC**: admin-only checks via `_is_user_admin()`.
- **ABAC**: NOT IMPLEMENTED (no ABAC checks in users module).
- **Gating**: onboarding token required.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/users`
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"email\":\"user@example.com\",\"roles\":[\"CLIENT_MANAGER\"]}" http://localhost/api/core/client/users/invite`

### Cards / Limits / Access (bulk)
- **Routes/API**: `/client/cards`, `/client/cards/{id}`, `/client/cards/{id}/limits`, `/client/cards/{id}/access`, bulk endpoints for block/unblock/access/limit templates.
- **RBAC**: `_is_card_admin()` for admin-only actions; access checks in `_ensure_card_access()`.
- **ABAC**: driver access enforced via card access scope + `_ensure_driver_user()`.
- **Gating**: billing entitlements enforced for write operations.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/cards`
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"card_ids\":[\"card-1\"],\"user_id\":\"driver-1\",\"scope\":\"LIMITED\"}" http://localhost/api/core/client/cards/bulk/access/grant`

### Fleet (cards/limits/access + notifications)
- **Routes/API**: `/api/client/fleet/cards`, `/api/client/fleet/groups`, `/api/client/fleet/limits`, `/api/client/fleet/notifications/*`.
- **RBAC**: permission-guarded (`require_permission(Permission.CLIENT_FLEET_*)`).
- **ABAC**: NOT IMPLEMENTED (fleet module uses RBAC + client_id scoping).
- **Gating**: `enforce_entitlement()` on write access (billing policy).
- **Ownership note**: `/api/client/fleet/*` is still the mounted fleet owner surface in the current topology; there is no live `/api/core/client/fleet/*` handoff yet.
- **Evidence**: `platform/processing-core/app/routers/client_fleet.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/client/fleet/cards`

### Documents
- **Routes/API**:
  - Canonical general docflow: `/api/core/client/documents*`
  - Portal read/download projections: `/api/core/client/docs/list`, `/api/core/client/docs/{document_id}/download`, `/api/core/client/docs/contracts/*`, `/api/core/client/docs/invoices`
  - Legacy closing-doc compatibility: `/api/v1/client/documents`, `/api/v1/client/documents/{document_id}`, `/api/v1/client/documents/{document_id}/download`
  - Manual-ack compatibility tails: `/api/v1/client/documents/{document_type}/{document_id}/ack`, `/api/v1/client/closing-packages/{package_id}/ack`
  - Frontend entry split: `/client/documents*` is the canonical general documents shell; `/documents/:id` remains the final legacy detail/file/history compatibility tail.
- **RBAC**: client token required.
- **ABAC**: `require_abac("documents:download")` on downloads + ABAC resource builder.
- **Gating**: `assert_module_enabled(..., module_code="DOCS")`.
- **Ownership note**: `/api/core/client/documents*` is the canonical general owner surface; `/api/v1/client/documents*` stays frozen for closing docs and manual-ack semantics and must not be treated as the default client documents API.
- **Evidence**: `platform/processing-core/app/routers/client_documents_v1.py`, `platform/processing-core/app/routers/client_documents.py`, `platform/processing-core/app/routers/client_portal_v1.py`, `platform/processing-core/app/tests/test_client_documents_ownership_truth.py`, `frontends/client-portal/src/App.documents-routing.test.tsx`.
- **How to verify (Windows CMD)**:
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/documents`
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/v1/client/documents`
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" http://localhost/api/v1/client/documents/INVOICE_PDF/%INVOICE_ID%/ack`

### Marketplace / Fleet stubs gating
- **Marketplace routes**: `/client/marketplace/products`, `/client/marketplace/products/{id}`, `/client/marketplace/recommendations`.
- **Gating**: client token required; no explicit module gating in marketplace router.
- **Evidence**: `platform/processing-core/app/routers/client_marketplace.py`.
- **NOT IMPLEMENTED**: explicit marketplace module gating by plan/entitlements not found in router.

### Support (tickets + comments + attachments + SLA + helpdesk outbound/inbound)
- **Routes/API**: `/client/support/tickets`, `/client/support/tickets/{id}`, `/client/support/tickets/{id}/comments`, `/client/support/tickets/{id}/attachments/*`.
- **SLA**: `initialize_support_ticket_sla`, `mark_first_response`, `mark_resolution`, breach audit events.
- **Helpdesk outbound**: helpdesk integration endpoints in `/client/helpdesk/integration` + outbound outbox.
- **Helpdesk inbound**: webhook handler applies inbound events to tickets.
- **RBAC/ABAC**: admin vs creator ticket scoping via `_is_support_ticket_admin()`; no explicit ABAC.
- **Gating**: billing entitlements required for outbound helpdesk integration.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`, `platform/processing-core/app/services/support_ticket_sla.py`, `platform/processing-core/app/routers/helpdesk_webhooks.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"subject\":\"Help\",\"message\":\"Test\",\"priority\":\"NORMAL\"}" http://localhost/api/core/client/support/tickets`

### Audit viewer
- **Routes/API**: `/client/audit/events` + `/client/audit/events/export`.
- **RBAC**: portal role filtering via `_audit_allowed_entity_types()`.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/audit/events`

### Reports / Exports
- **Exports (async jobs)**: `/client/exports/jobs` create/list/get/download; Celery task `exports.generate_export_job` streams report render results.
- **Formats**: CSV + XLSX; XLSX gated by entitlements and format enum.
- **ETA**: export job response includes `eta_seconds` + `eta_at`.
- **Scheduled reports**: `/client/reports/schedules` CRUD + background scheduler task `reports.run_report_schedules`.
- **Retention/cleanup**: export jobs include `expires_at` and cleanup task `exports.cleanup_expired_exports` on schedule.
- **Large exports streaming/chunking**: render/export uses `render_export_report_stream` with chunk size, writes streaming CSV/XLSX.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`, `platform/processing-core/app/schemas/client_portal_v1.py`, `platform/processing-core/app/tasks/export_jobs.py`, `platform/processing-core/app/celery_client.py`, `platform/processing-core/app/services/reports_render.py`.
- **How to verify (Windows CMD)**:
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"report_type\":\"CARDS\",\"format\":\"CSV\",\"filters\":{}}" http://localhost/api/core/client/exports/jobs`

## 3.6 Commercial & Finance (AS-IS)

**Pricing & plans in DB (schema + seed)**
- Schema: `subscription_plans`, `subscription_plan_features`, `subscription_plan_modules`, `org_subscriptions`, `org_entitlements_snapshot`.
- Seed: `db/init/02_seed_catalog_v1.sql` inserts subscription plans + features + addons.
- **Evidence**: `db/init/01_schema.sql`, `db/init/02_seed_catalog_v1.sql`.
- **How to verify (Windows CMD)**: `psql -f db/init/01_schema.sql`

**Billing accounts / invoices / lines**
- Tables exist (`billing_accounts`, `billing_invoices`, `billing_invoice_lines`).
- **Evidence**: `db/init/01_schema.sql`, `platform/processing-core/app/repositories/billing_repository.py`.
- **How to verify (Windows CMD)**: `curl -i -H "Authorization: Bearer %ADMIN_TOKEN%" http://localhost/api/core/v1/admin/billing/invoices`

**Invoice generator (beat schedules)**
- Celery beat schedules for subscription invoice generation + invoice PDF generation.
- **Evidence**: `platform/processing-core/app/celery_client.py`, `platform/processing-core/app/tasks/billing_pdf.py`.
- **How to verify (Windows CMD)**: `curl -i -X POST -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -d "{\"period_from\":\"2024-01-01\",\"period_to\":\"2024-01-31\",\"status\":\"ISSUED\"}" http://localhost/api/core/v1/admin/billing/invoices/generate`

**Payment intake (manual proof + approve/reject)**
- Client submits payment intake via `/client/invoices/{invoice_id}/payment-intakes` + attachment init.
- Admin reviews via `/api/core/v1/admin/billing/payment-intakes/{id}/approve|reject`.
- Ownership note: canonical client-portal-v1 invoice flow lives under `/api/core/client/invoices*`; legacy `/api/client/invoices*` from `portal.py` remains a separate public billing projection around `invoice_ref`/`Invoice` and is not route-parity with the canonical subscription invoice owner.
- **Evidence**: `platform/processing-core/app/routers/client_portal_v1.py`, `platform/processing-core/app/routers/admin/billing_payment_intakes.py`.
- **How to verify (Windows CMD)**: `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"amount\":1000,\"currency\":\"RUB\"}" http://localhost/api/core/client/invoices/%INVOICE_ID%/payment-intakes`

**Dunning flow + auto-suspend + suspend_blocked_until**
- Dunning scan + auto-suspend tasks (`billing.dunning_scan`, `billing.suspend_overdue`) scheduled via Celery beat.
- Auto-suspend respects `suspend_blocked_until` if present.
- **Evidence**: `platform/processing-core/app/services/billing_dunning.py`, `platform/processing-core/app/tasks/billing_dunning.py`, `platform/processing-core/app/celery_client.py`.
- **How to verify (Windows CMD)**: `curl -i -H "Authorization: Bearer %ADMIN_TOKEN%" http://localhost/api/core/v1/admin/billing/invoices`

**Bank reconciliation**
- Import supports CSV + 1C + MT940 formats via reconciliation imports.
- Reconciliation runs + discrepancies with manual resolve/ignore endpoints.
- Fixtures generator endpoints available (API).
- Fixtures generator UI: **NOT IMPLEMENTED** (no UI found in repo).
- **Evidence**: `platform/processing-core/app/schemas/admin/reconciliation_imports.py`, `platform/processing-core/app/routers/admin/reconciliation_imports.py`, `platform/processing-core/app/routers/admin/reconciliation.py`.
- **How to verify (Windows CMD)**: `curl -i -H "Authorization: Bearer %ADMIN_TOKEN%" http://localhost/api/core/v1/admin/reconciliation/imports`

**Revenue dashboard admin**
- Admin revenue endpoints: `/api/core/v1/admin/revenue/summary|overdue|usage`.
- **Evidence**: `platform/processing-core/app/routers/admin/revenue.py`.
- **How to verify (Windows CMD)**: `curl -i -H "Authorization: Bearer %ADMIN_TOKEN%" http://localhost/api/core/v1/admin/revenue/summary`

**Contract pack generator + listing**
- Admin endpoints: `/api/core/v1/admin/contract-packs` (generate + list).
- **Evidence**: `platform/processing-core/app/routers/admin/contract_packs.py`, `platform/processing-core/app/services/contract_pack_service.py`.
- **How to verify (Windows CMD)**: `curl -i -H "Authorization: Bearer %ADMIN_TOKEN%" http://localhost/api/core/v1/admin/contract-packs`

## 3.7 Observability (AS-IS)

**Metrics added**
- Core API exposes `/api/core/metrics`, including exports, email outbox, report schedules, support/cases, notifications, reconciliation, etc.

**Prometheus rules**
- `infra/prometheus_rules.yml` exists.

**Grafana dashboard “Client Ops”**
- Dashboard JSON: `infra/grafana/dashboards/client_ops.json`.

**Where files live**
- Metrics: `platform/processing-core/app/main.py` (metrics endpoint aggregator).
- Grafana: `infra/grafana/dashboards/`.

**Evidence (files/endpoints)**:
- `platform/processing-core/app/main.py` (metrics endpoint includes exports/email/schedules/notifications/cases).
- `infra/prometheus_rules.yml` (Prometheus rules).
- `infra/grafana/dashboards/client_ops.json` (Grafana dashboard).

**How to verify (Windows CMD)**:
- `curl -i http://localhost/api/core/metrics`

## 3.8 Runbooks / Smoke

**Windows smoke scripts (actual files)**
- `scripts\smoke_client_portal.cmd` (portal load + auth login/register + core health).
- `scripts\billing_smoke.cmd` (admin billing periods/run/invoices/pdf).
- `scripts\smoke_support_ticket.cmd` — real compatibility support-request -> canonical case smoke.
- `scripts\smoke_operations_explain.cmd` — real operations list/detail + KPI explain smoke.
- `scripts\smoke_reconciliation_request_sign.cmd` — real reconciliation request -> attach result -> download -> ack smoke.
- `scripts\smoke_cards_issue.cmd` — real seeded card status-cycle smoke.
- `scripts\smoke_limits_apply_and_enforce.cmd` — real card limit apply/read smoke.
- `scripts\smoke_client_users_roles.cmd` — real client users/roles smoke (`register -> login -> verify -> me -> portal/me -> users -> role update -> invite -> resend -> revoke`) over mounted owner routes.
- `scripts\smoke_reconciliation_run.cmd` — real admin reconciliation smoke over canonical `/api/core/v1/admin/reconciliation/*` routes.

**Minimum bring-up (local)**
- Use `docker compose up -d` (standard local stack).

**Mandatory verification commands (Windows CMD)**
- `/client/ loads`
  - `curl -i http://localhost/client/`
- `/api/core/health`
  - `curl -i http://localhost/api/core/health`
- `/api/core/client/me` (401 without token + 200 with token)
  - `curl -i http://localhost/api/core/client/me`
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/me`
- Exports job create
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"report_type\":\"CARDS\",\"format\":\"CSV\",\"filters\":{}}" http://localhost/api/core/client/exports/jobs`
- Invoice list
  - `curl -i -H "Authorization: Bearer %TOKEN%" http://localhost/api/core/client/invoices`
- Payment intake submit
  - `curl -i -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"amount\":1000,\"currency\":\"RUB\",\"payer_name\":\"Test LLC\",\"payer_inn\":\"1234567890\",\"paid_at_claimed\":\"2024-01-01T00:00:00Z\"}" http://localhost/api/core/client/invoices/%INVOICE_ID%/payment-intakes`
- Reconciliation import
  - `curl -i -X POST -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -d "{\"file_name\":\"statement.csv\",\"content_type\":\"text/csv\",\"format\":\"CSV\"}" http://localhost/api/core/v1/admin/reconciliation/imports`
  - `curl -i -X PUT --upload-file statement.csv "%UPLOAD_URL%"`
  - `curl -i -X POST -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -d "{\"object_key\":\"%OBJECT_KEY%\"}" http://localhost/api/core/v1/admin/reconciliation/imports/%IMPORT_ID%/complete`

**Known limitations (code evidence only)**
- OTP-based signup not found in auth-host; only register/login flows exist.
- Global uncaught-error boundary exists in `frontends/client-portal/src/components/ErrorBoundary.tsx`; explicit client failure pages exist in `frontends/client-portal/src/pages/ServiceUnavailablePage.tsx` and `frontends/client-portal/src/pages/TechErrorPage.tsx`.
- Client auth/bootstrap and the compose-gate onboarding review/approve/doc-signing/docflow smokes are no longer stubbed; remaining client gaps are product/UI contours rather than placeholder smoke entrypoints.

---

**Current milestone — Client Portal is v1.4 feature complete; remaining items:** OTP signup and any UI for reconciliation fixtures/support smoke workflows not found in code (NOT IMPLEMENTED). Explicit error pages/uncaught error handling are already present in the portal shell.

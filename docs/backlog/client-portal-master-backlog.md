# Client Portal — Master Backlog (P0/P1 + P2)

Source of truth: SSoT `GET /api/core/portal/me`. UI must derive access states only from this payload, never from ad‑hoc error handling or admin portals. This backlog enumerates the work to deliver Scope v1 and formalize the Client Portal contract and DoD.

## MVP Backlog (P0/P1) — 24 items

1) **P0 — Formalize SSoT access_state/gating block in `/portal/me`**
   - **Why:** AccessState screens must be driven by explicit SSoT fields (org/subscription/modules/capabilities + gating flags). Currently `PortalMeResponse` exposes `features` and `flags`, but no explicit `access_state` block. Define and document a stable contract.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/schemas/portal_me.py`, `platform/processing-core/app/services/portal_me.py`, `docs/as-is/CLIENT_PORTAL_AS_IS_MASTER.md`, `docs/runbook/client_portal_e2e.md`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** `portal/me` includes `gating` and/or `access_state` with `state` + `reason_code` (if already present, only document). Feature flags include `onboarding_enabled` as gate.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

2) **P0 — Map canonical Access States to existing SSoT fields**
   - **Why:** Required UI states (`AUTH_REQUIRED`, `NEEDS_ONBOARDING`, `NEEDS_PLAN`, `OVERDUE`, `SUSPENDED`, `MISSING_CAPABILITY`, `MODULE_DISABLED`, `FORBIDDEN_ROLE`, `SERVICE_UNAVAILABLE`, `MISCONFIG`, `TECH_ERROR`) must be derived from org/subscription/entitlements/capabilities/gating flags.
   - **Owner:** client-portal + core-api
   - **Files:** `frontends/client-portal/src/access/accessState.ts`, `platform/processing-core/app/schemas/portal_me.py`, `docs/runbook/client_portal_e2e.md`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** Documented mapping of SSoT → AccessState; `SERVICE_UNAVAILABLE` only for 502/503/network; `TECH_ERROR` only for 5xx parse/crash; `MISCONFIG` dev-only.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

3) **P0 — Ensure `/portal/me` never 500 for valid token**
   - **Why:** bootstrap must return structured error payloads with `request_id` + `error_id`/`reason_code`.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/services/portal_me.py`, `platform/processing-core/app/routers/portal_me.py`, error middleware
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** Any failure returns `4xx/5xx` with structured error + `request_id`; no uncaught exceptions for valid tokens.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

4) **P0 — dev_seed_core.py schema parity**
   - **Why:** seed should not fail on missing columns (e.g., `clients.email`).
   - **Owner:** core-api
   - **Files:** `scripts/dev_seed_core.py`
   - **API:** none
   - **DB:** `clients`
   - **DoD:** seed script runs on latest schema without errors.
   - **Smoke (CMD):** `docker compose exec -T core-api python scripts/dev_seed_core.py`

5) **P0 — Admin demo credentials alignment**
   - **Why:** demos must not drift across environments (`admin@example.com` vs `admin@neft.local`).
   - **Owner:** auth-host + docs
   - **Files:** `docs/runbooks/DEMO_USERS_AND_LOGIN.md`, auth-host seed/config
   - **API:** `/api/auth/login`
   - **DB:** auth-host users
   - **DoD:** single documented admin demo credential across envs.
   - **Smoke (CMD):** `curl -i %AUTH_BASE%/login -H "Content-Type: application/json" -d @admin_login.json`

6) **P1 — Confirm onboarding gating flag exposed in SSoT**
   - **Why:** UI already shows “Onboarding disabled by admin”; must be driven by `features.onboarding_enabled` in SSoT.
   - **Owner:** core-api + client-portal
   - **Files:** `platform/processing-core/app/schemas/portal_me.py`, `platform/processing-core/app/services/portal_me.py`, `frontends/client-portal/src/components/Layout.tsx`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** `features.onboarding_enabled=false` yields CTA or blocked state (no 404/500).
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

7) **P1 — Org missing → NEEDS_ONBOARDING**
   - **Why:** `org=null` should always route to onboarding CTA.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/services/portal_me.py`, `frontends/client-portal/src/access/accessState.ts`
   - **API:** `GET /api/core/portal/me`
   - **DB:** `clients`, `orgs`
   - **DoD:** when org is null, access state is `NEEDS_ONBOARDING` with reason `org_not_active`.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

8) **P1 — Create org draft for onboarding**
   - **Why:** onboarding flow needs backend to create a draft org.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_onboarding.py`
   - **API:** `POST /api/core/client/org`
   - **DB:** `clients` / `crm_clients`
   - **DoD:** endpoint creates DRAFT/ONBOARDING org and returns ID; SSoT returns org in bootstrap.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/client/org -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{}"`

9) **P1 — Select plan/modules**
   - **Why:** plan + modules must be captured before activation.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_onboarding.py`, `platform/processing-core/app/services/entitlements_v2_service.py`
   - **API:** `POST /api/core/client/subscription/select`
   - **DB:** `subscription_plans`, `subscription_plan_modules`, `client_subscriptions`, `org_entitlements_snapshot`
   - **DoD:** selecting plan updates entitlements snapshot and SSoT subscription.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/client/subscription/select -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"plan_code\":\"BASIC\",\"modules\":[\"FLEET\"]}"`

10) **P1 — Generate contract pack**
   - **Why:** legal contract generation needed for onboarding.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/services/contract_pack_service.py`, `platform/processing-core/app/routers/client_onboarding.py`
   - **API:** `POST /api/core/client/contracts/generate`
   - **DB:** `crm_contracts`, `client_onboarding_contracts`
   - **DoD:** generated contract pack stores snapshot hash and is downloadable.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/client/contracts/generate -H "Authorization: Bearer %CLIENT_TOKEN%"`

11) **P1 — Sign contract (OTP/ПЭП)**
   - **Why:** finalize legal docs before activation.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_onboarding.py`
   - **API:** `POST /api/core/client/contracts/sign`
   - **DB:** `crm_contracts`, `client_onboarding_contracts`
   - **DoD:** successful sign updates contract status; SSoT indicates legal acceptance.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/client/contracts/sign -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"otp\":\"0000\"}"`

12) **P1 — Activation step**
   - **Why:** finish onboarding by setting org/subscription ACTIVE.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_onboarding.py`
   - **API:** `POST /api/core/client/onboarding/activate`
   - **DB:** `clients`, `client_subscriptions`, `org_entitlements_snapshot`
   - **DoD:** SSoT returns `org.status=ACTIVE` and `subscription.status=ACTIVE`.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/client/onboarding/activate -H "Authorization: Bearer %CLIENT_TOKEN%"`

13) **P1 — Driver ABAC enforcement for cards**
   - **Why:** DRIVER sees only assigned cards or explicit CardAccess (VIEW/USE).
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/models/client_portal.py`, `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `/api/core/v1/client/cards`, `/api/core/v1/client/cards/{id}`
   - **DB:** `card_access`, `cards`
   - **DoD:** driver list filters by `assigned_driver_user_id` or `card_access` scope; OWNER sees all.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards -H "Authorization: Bearer %DRIVER_TOKEN%"`

14) **P1 — Users: list/invite/assign roles/disable**
   - **Why:** OWNER/ADMIN manage client portal users; DRIVER restricted.
   - **Owner:** core-api + client-portal
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`, `frontends/client-portal/src/pages/FleetEmployeesPage.tsx`
   - **API:** `GET /api/core/v1/client/users`, `POST /api/core/v1/client/users/invite`, `PATCH /api/core/v1/client/users/{id}/roles`, `DELETE /api/core/v1/client/users/{id}`
   - **DB:** `client_employees`, `client_user_roles`
   - **DoD:** OWNER/ADMIN can manage; DRIVER denied with `403` + reason_code.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/users -H "Authorization: Bearer %CLIENT_TOKEN%"`

15) **P1 — Cards: list/issue/block/limits/assign**
   - **Why:** Active clients need card management.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`, `platform/processing-core/app/models/client_portal.py`
   - **API:** `GET /api/core/v1/client/cards`, `POST /api/core/v1/client/cards/issue`, `POST /api/core/v1/client/cards/{id}/block`, `POST /api/core/v1/client/cards/{id}/limits`
   - **DB:** `client_cards`, `card_limits`
   - **DoD:** operations return `403` with `reason_code` on denied access.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards -H "Authorization: Bearer %CLIENT_TOKEN%"`

16) **P1 — CardAccess grant/revoke**
   - **Why:** Allow OWNER/ADMIN to grant VIEW/USE to drivers.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/models/client_portal.py`, `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `POST /api/core/v1/client/cards/{card_id}/access`, `DELETE /api/core/v1/client/cards/{card_id}/access/{user_id}`
   - **DB:** `card_access`
   - **DoD:** grant/revoke audited; changes reflected in driver card list.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/v1/client/cards/%CARD_ID%/access -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"user_id\":\"%DRIVER_ID%\",\"scope\":\"VIEW\"}"`

17) **P1 — Documents list + signed URL download**
   - **Why:** ACCOUNTANT should access contracts/invoices/acts.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_documents.py`, `platform/processing-core/app/models/crm.py`, `platform/processing-core/app/models/invoice.py`
   - **API:** `GET /api/core/client/documents`, `GET /api/core/client/documents/{id}/download`
   - **DB:** `crm_contracts`, `invoices`
   - **DoD:** ACCOUNTANT can list/download; DRIVER denied with `403` + reason_code.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/client/documents -H "Authorization: Bearer %CLIENT_TOKEN%"`

18) **P1 — Reports/Exports foundation**
   - **Why:** Migrate exports to explicit export job model.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/models/export_jobs.py`, `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `POST /api/core/v1/client/exports`, `GET /api/core/v1/client/exports`, `GET /api/core/v1/client/exports/{id}`
   - **DB:** `export_jobs`
   - **DoD:** Export jobs created + status returned; download when ready.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/v1/client/exports -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"report_type\":\"USERS\",\"format\":\"CSV\"}"`

19) **P1 — Menu gating doc + policy enforcement**
   - **Why:** nav must align with entitlements/modules/capabilities (no 404 when disabled).
   - **Owner:** client-portal
   - **Files:** `frontends/client-portal/src/components/Layout.tsx`, `docs/client-portal/menu-policy.md`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** menu policy map documented and enforced; disabled entries show CTA.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

20) **P1 — AccessState screens for business states (no generic errors)**
   - **Why:** no “just error” for business state (needs plan, overdue, suspended, missing capability, module disabled).
   - **Owner:** client-portal
   - **Files:** `frontends/client-portal/src/access/accessState.ts`, status pages
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** UX shows state-specific CTA; 403+reason_code mapped to AccessState.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

21) **P1 — Standard error payloads w/ reason_code**
   - **Why:** UI must show proper AccessState for 403/409/422.
   - **Owner:** core-api
   - **Files:** error handlers + relevant routers
   - **API:** client portal endpoints
   - **DB:** none
   - **DoD:** all rejected actions return `reason_code` (e.g., `module_disabled`, `missing_capability`) and `request_id`.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards -H "Authorization: Bearer %DRIVER_TOKEN%"`

22) **P1 — Validate portal/me contract test**
   - **Why:** protect SSoT fields.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/tests/test_portal_me_contract.py`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** tests assert `user`, `org`, `subscription`, `entitlements_snapshot`, `capabilities`, `features`.
   - **Smoke (CMD):** `docker compose exec -T core-api pytest app/tests/test_portal_me_contract.py`

23) **P1 — Client portal onboarding CTA wiring**
   - **Why:** if onboarding disabled or missing org, UI must render CTA not error.
   - **Owner:** client-portal
   - **Files:** `frontends/client-portal/src/components/Layout.tsx`, `frontends/client-portal/src/pages/OnboardingPage.tsx`
   - **API:** `GET /api/core/portal/me`
   - **DB:** none
   - **DoD:** onboarding CTA shown for `NEEDS_ONBOARDING`; disabled state shows “Contact manager”.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

24) **P1 — Docs: client-domain-map + E2E runbook**
   - **Why:** ensure canonical model alignment + reproducible scenarios.
   - **Owner:** docs
   - **Files:** `docs/as-is/client-domain-map.md`, `docs/runbook/client_portal_e2e.md`
   - **API:** multiple (see runbook)
   - **DB:** multiple (see runbook)
   - **DoD:** docs list model/migration/routes per entity and smoke steps for Scenario A.
   - **Smoke (CMD):** `type docs\\runbook\\client_portal_e2e.md`

---

## P2 Backlog — 24 items

1) **P2 — Overdue billing flow in Client Portal**
   - **Why:** `OVERDUE` state should show payment CTA and recovery.
   - **Owner:** core-api + client-portal
   - **Files:** billing routers, access state screens
   - **API:** billing endpoints + `GET /api/core/portal/me`
   - **DB:** `client_subscriptions`, `billing_invoices`
   - **DoD:** overdue status leads to payment page; after payment SSoT → `ACTIVE`.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

2) **P2 — Driver-only view for operations**
   - **Why:** drivers see only their transactions.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `/api/core/v1/client/operations`
   - **DB:** `operations`, `card_access`
   - **DoD:** driver query filtered by assigned card or access.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/operations -H "Authorization: Bearer %DRIVER_TOKEN%"`

3) **P2 — Support tickets CRUD**
   - **Why:** customer support workflow in portal.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `/api/core/v1/client/support/tickets`
   - **DB:** support ticket tables
   - **DoD:** create/list/update/close tickets with attachments.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/support/tickets -H "Authorization: Bearer %CLIENT_TOKEN%"`

4) **P2 — Ticket attachments**
   - **Why:** support workflow requires files.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`, storage service
   - **API:** `/api/core/v1/client/support/tickets/{id}/attachments`
   - **DB:** attachment tables
   - **DoD:** signed URL upload + download.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/support/tickets/%ID%/attachments -H "Authorization: Bearer %CLIENT_TOKEN%"`

5) **P2 — SLA state tracking for support**
   - **Why:** show SLA timers in UI.
   - **Owner:** core-api + client-portal
   - **Files:** support models + client UI pages
   - **API:** support endpoints
   - **DB:** SLA fields on ticket table
   - **DoD:** UI shows SLA status and countdowns.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/support/tickets -H "Authorization: Bearer %CLIENT_TOKEN%"`

6) **P2 — Reports export job progress**
   - **Why:** improve export UX with progress/ETA.
   - **Owner:** core-api + client-portal
   - **Files:** `platform/processing-core/app/models/export_jobs.py`, export endpoints
   - **API:** `GET /api/core/v1/client/exports/{id}`
   - **DB:** `export_jobs`
   - **DoD:** progress fields populated and displayed.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/exports/%ID% -H "Authorization: Bearer %CLIENT_TOKEN%"`

7) **P2 — Fleet module AccessState parity**
   - **Why:** fleet API returns `unavailable` only for real service outages.
   - **Owner:** client-portal + core-api
   - **Files:** `frontends/client-portal/src/api/fleet.ts`
   - **API:** fleet endpoints
   - **DB:** fleet tables
   - **DoD:** `SERVICE_UNAVAILABLE` only on 502/503/network.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/client/fleet/vehicles -H "Authorization: Bearer %CLIENT_TOKEN%"`

8) **P2 — Documents: acts/invoices/contract categories**
   - **Why:** align documents with canonical types.
   - **Owner:** core-api
   - **Files:** `platform/processing-core/app/routers/client_documents.py`
   - **API:** `/api/core/client/documents`
   - **DB:** `crm_contracts`, `invoices`, docs tables
   - **DoD:** filters by doc type with reason codes.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/client/documents?type=invoice -H "Authorization: Bearer %CLIENT_TOKEN%"`

9) **P2 — Card limits UI**
   - **Why:** show card limits per user/vehicle.
   - **Owner:** client-portal
   - **Files:** card pages/components
   - **API:** limits endpoints
   - **DB:** `card_limits`
   - **DoD:** limits displayed with edit CTA.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards/%CARD_ID%/limits -H "Authorization: Bearer %CLIENT_TOKEN%"`

10) **P2 — Bulk user invite**
   - **Why:** orgs need batch onboarding.
   - **Owner:** core-api + client-portal
   - **Files:** `platform/processing-core/app/routers/client_portal_v1.py`
   - **API:** `POST /api/core/v1/client/users/invite/bulk`
   - **DB:** `client_employees`, `client_user_roles`
   - **DoD:** bulk invite returns per-row status.
   - **Smoke (CMD):** `curl -i -X POST %GATEWAY_BASE%/api/core/v1/client/users/invite/bulk -H "Authorization: Bearer %CLIENT_TOKEN%" -d @users.csv`

11) **P2 — User role audit trail**
   - **Why:** compliance for role changes.
   - **Owner:** core-api
   - **Files:** audit service + user role endpoints
   - **API:** `PATCH /api/core/v1/client/users/{id}/roles`
   - **DB:** audit log tables
   - **DoD:** role changes recorded with request_id.
   - **Smoke (CMD):** `curl -i -X PATCH %GATEWAY_BASE%/api/core/v1/client/users/%ID%/roles -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"roles\":[\"CLIENT_ADMIN\"]}"`

12) **P2 — Card issue seed for demo**
   - **Why:** demo clients should have initial cards.
   - **Owner:** core-api
   - **Files:** `scripts/dev_seed_core.py`
   - **API:** none
   - **DB:** `client_cards`
   - **DoD:** seed creates cards per demo client.
   - **Smoke (CMD):** `docker compose exec -T core-api python scripts/dev_seed_core.py`

13) **P2 — Capability catalog documentation**
   - **Why:** unify capability names used in UI.
   - **Owner:** core-api + docs
   - **Files:** `app/services/entitlements_v2_service.py`, docs
   - **API:** `GET /api/core/portal/me`
   - **DB:** `role_entitlements`
   - **DoD:** documented list of capabilities + modules.
   - **Smoke (CMD):** `curl -s %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

14) **P2 — Driver card access UI**
   - **Why:** Owner can grant VIEW/USE from UI.
   - **Owner:** client-portal
   - **Files:** card detail pages
   - **API:** card access endpoints
   - **DB:** `card_access`
   - **DoD:** grant/revoke visible with success toasts.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards/%CARD_ID%/access -H "Authorization: Bearer %CLIENT_TOKEN%"`

15) **P2 — Export download authorization**
   - **Why:** ensure only roles can download exports.
   - **Owner:** core-api
   - **Files:** export endpoints
   - **API:** `GET /api/core/v1/client/exports/{id}/download`
   - **DB:** `export_jobs`
   - **DoD:** DRIVER forbidden; OWNER allowed.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/exports/%ID%/download -H "Authorization: Bearer %CLIENT_TOKEN%"`

16) **P2 — Reports list for ACCOUNTANT**
   - **Why:** finance users need reports without cards access.
   - **Owner:** client-portal
   - **Files:** reports pages
   - **API:** export endpoints
   - **DB:** export tables
   - **DoD:** ACCOUNTANT sees reports only; cards hidden.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/exports -H "Authorization: Bearer %ACCOUNTANT_TOKEN%"`

17) **P2 — Driver onboarding flow**
   - **Why:** driver accept invitation and view assigned cards.
   - **Owner:** auth-host + client-portal
   - **Files:** auth onboarding flows + client pages
   - **API:** auth invite endpoints
   - **DB:** auth user tables, `client_employees`
   - **DoD:** driver login → portal/me shows restricted views.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %DRIVER_TOKEN%"`

18) **P2 — Docs download access audit**
   - **Why:** track document downloads.
   - **Owner:** core-api
   - **Files:** document endpoints + audit
   - **API:** `GET /api/core/client/documents/{id}/download`
   - **DB:** audit tables
   - **DoD:** download creates audit record.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/client/documents/%ID%/download -H "Authorization: Bearer %CLIENT_TOKEN%"`

19) **P2 — Portal cache safety**
   - **Why:** portal must work without cache.
   - **Owner:** core-api
   - **Files:** entitlements services
   - **API:** `GET /api/core/portal/me`
   - **DB:** entitlements snapshots
   - **DoD:** cold boot without cache returns SSoT correctly.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

20) **P2 — Request_id propagation verification**
   - **Why:** traceability across core-api.
   - **Owner:** core-api
   - **Files:** middleware
   - **API:** all client endpoints
   - **DB:** none
   - **DoD:** `request_id` appears on all responses.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards -H "Authorization: Bearer %CLIENT_TOKEN%"`

21) **P2 — Entitlements snapshot history UI**
   - **Why:** help admins debug client access.
   - **Owner:** admin portal + core-api
   - **Files:** admin entitlements endpoints
   - **API:** `/api/core/admin/commercial/entitlements-snapshots`
   - **DB:** `org_entitlements_snapshot`
   - **DoD:** admin can view current/previous snapshots.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/admin/commercial/entitlements-snapshots?org_id=%ORG_ID% -H "Authorization: Bearer %ADMIN_TOKEN%"`

22) **P2 — Service unavailable guardrails**
   - **Why:** ensure `SERVICE_UNAVAILABLE` only for 502/503/network errors.
   - **Owner:** client-portal
   - **Files:** access state handlers
   - **API:** client endpoints
   - **DB:** none
   - **DoD:** 4xx/5xx mapped to business states or TECH_ERROR; 502/503→SERVICE_UNAVAILABLE.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/v1/client/cards -H "Authorization: Bearer %CLIENT_TOKEN%"`

23) **P2 — Plan upgrade CTA**
   - **Why:** module disabled should lead to upgrade flow.
   - **Owner:** client-portal
   - **Files:** subscription page
   - **API:** subscription endpoints
   - **DB:** `subscription_plans`
   - **DoD:** module disabled shows CTA, not 404.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"`

24) **P2 — Legal gate UI polish**
   - **Why:** `legal_gate_enabled` requires clear UX.
   - **Owner:** client-portal
   - **Files:** legal gate components
   - **API:** `GET /api/core/legal/required`
   - **DB:** legal acceptance tables
   - **DoD:** legal gating shows required docs list + CTA.
   - **Smoke (CMD):** `curl -i %GATEWAY_BASE%/api/core/legal/required -H "Authorization: Bearer %CLIENT_TOKEN%"`


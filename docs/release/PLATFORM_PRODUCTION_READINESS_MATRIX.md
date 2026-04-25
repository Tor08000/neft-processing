# NEFT Platform Production Readiness Matrix

## Canonical seeded accounts

Runtime source of truth: `platform/auth-host/app/seeds/demo_users.py`

| Portal | Seeded account | Password | Intended use |
| --- | --- | --- | --- |
| Admin | `admin@neft.local` | `Neft123!` | operator/admin bootstrap, smoke, local verification |
| Client | `client@neft.local` | `Client123!` | client bootstrap, onboarding/dashboard verification |
| Partner | `partner@neft.local` | `Partner123!` | partner workspace bootstrap, finance/legal/support verification |

Seed rule:

- canonical seeded users are not hidden demo-only runtime fallbacks
- explicit showcase/demo behavior is allowed only when demo mode is enabled or a showcase contour is mounted on purpose

## Launch evidence lock

Current closeout source of truth: `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md`.

Repo hygiene source of truth:

- `docs/diag/REPO_HYGIENE_20260425.md`
- `docs/diag/RELEASE_PATCH_SLICES_20260425.md`
- `docs/diag/S1_S2_OWNER_REVIEW_20260425.md`
- `docs/diag/S3_S4_OWNER_REVIEW_20260425.md`
- `docs/diag/S5_ADMIN_UI_OWNER_REVIEW_20260425.md`
- `docs/diag/S6_CLIENT_PORTAL_OWNER_REVIEW_20260425.md`
- `docs/diag/S7_PARTNER_PORTAL_OWNER_REVIEW_20260425.md`
- `docs/diag/S8_SHARED_BRAND_OWNER_REVIEW_20260425.md`
- `docs/diag/S9_E2E_BROWSER_SMOKE_OWNER_REVIEW_20260425.md`
- `docs/diag/S11_SCRIPTS_SMOKES_OWNER_REVIEW_20260425.md`
- `docs/diag/S10_DOCS_EVIDENCE_OWNER_REVIEW_20260425.md`
- `docs/diag/S12_OPS_SNAPSHOT_OWNER_REVIEW_20260425.md`
- `docs/diag/S13_ROOT_MISC_RISKY_DELETIONS_REVIEW_20260425.md`
- `docs/diag/FINAL_PATHSPEC_GROUPS_20260425.md`

These files supersede the 2026-04-21 hygiene/slice docs for final PR packaging. They do not erase older runtime evidence; they lock the post-marketplace, external-provider, partner-finance, logistics, AI/risk, BI, and repo-hygiene state.

Current packaging rule:

- review by owner slices only, never `git add .`
- generated scratch is not launch evidence unless promoted under `docs/diag` and referenced from the evidence lock
- risky deletions remain owner-review items until replacement/freeze evidence exists
- remaining provider and optional tails keep the strict gate taxonomy below

## Canonical defect matrix

| Contour | Owner | Seeded account | Classification | Expected state | Current recovery status | Known blocker / note |
| --- | --- | --- | --- | --- | --- | --- |
| `/admin/marketplace/moderation` | admin-ui + `processing-core` moderation queue | `admin@neft.local` | runtime 4xx/5xx, weak state quality | queue loads or shows honest queue-empty / filtered-empty / retry | UI hardening plus backend missing-table/read-model guards landed | action/detail flows still depend on real moderation data being present |
| `/cases` | admin-ui + canonical `/api/core/cases*` | `admin@neft.local` | runtime 4xx/5xx, weak state quality | list loads or shows honest filtered-empty / retry | raw payload leak removed from primary UI | there is no separate admin list owner route to flip to safely |
| `/geo-analytics` | admin-ui + geo analytics reads | `admin@neft.local` | auth drift, runtime 4xx/5xx | tiles/drill-down load with admin token or show structured retry state | auth client source-fix plus backend empty-read-model guards landed | empty geo payload is honest when cache/read tables are absent; data population is still a separate readiness track |
| `/legal/documents` | admin-ui + `/api/core/v1/admin/legal*` | `admin@neft.local` | weak state quality, design-system drift | registry/acceptances load or show honest retry / empty / access-limited | operator surface hardened and backend list routes now degrade to explicit empty when legal tables are not bootstrapped | create/update/publish still require the canonical legal tables and stay strict by design |
| `/legal/partners` | admin-ui + `/api/core/v1/admin/legal/partners*` | `admin@neft.local` | weak state quality | partner list/detail loads or shows honest retry / empty | list surface now degrades to explicit empty when partner legal tables are absent | detail/load failures still need deeper backend stability work if legal partner tables are missing |
| `/dashboard` (client) | client-portal + `/api/core/client/dashboard` + `/api/core/portal/me` | `client@neft.local` | identity/demo drift, runtime/auth drift | real dashboard or honest first-use/access-limited/retry | hidden demo fallback disabled outside demo mode; backend bootstrap response and missing-read guards landed | populated widgets still depend on real client/read-model data being present |
| `/logistics` (client) | client-portal + `/api/core/client/logistics*` | `client@neft.local` | fake/read drift, weak frozen-tail semantics | fleet/trips/fuel load from persisted owner routes; trip create persists order/route/stops with preview-backed snapshot evidence; fuel-consumption analytics reads are mounted; provider-backed consumption writes return sandbox-backed evidence | client logistics reads now use shared-storage-safe queries, trip create is mounted in the client UI, and live smoke covers fleet/trips/fuel/create/consumption analytics plus provider-backed fuel-consumption write `200` | production external fleet/fuel credentials remain outside the internal gate |
| client shell bootstrap | client-portal + `/api/core/portal/me` | `client@neft.local` | identity/demo drift | canonical seed uses live bootstrap truth | hidden demo/showcase bypass removed outside explicit demo mode | onboarding/access-state semantics still depend on `portal/me` truth |
| partner workspace bootstrap | partner-portal + partner APIs | `partner@neft.local` | identity/demo drift | canonical seed uses live workspace truth | mounted `/onboarding` owner route now handles pending partners without hidden demo/profile fallback | broader partner runtime parity still remains a later slice |
| shared visual shell | `frontends/shared/brand` | all three | design-system drift | one Dark NEFT Premium system across portals | tokens shifted to gold-primary / blue-accent direction; S8 shared brand owner review locks component/token ownership and portal import guards | route/page-level adoption remains gradual |

## Seeded owner-route smoke coverage

| Contour | Backend seeded smoke | Current truth |
| --- | --- | --- |
| admin marketplace moderation | `app/tests/test_seeded_portal_route_smoke.py::test_admin_marketplace_seeded_queue_smoke` | seeded moderation queue returns pending product/service/offer items for admin owner route |
| admin geo analytics | `app/tests/test_seeded_portal_route_smoke.py::test_admin_geo_seeded_route_smoke` | seeded tiles, overlays, and station metrics load together without raw internal-error fallback |
| admin legal registry | `app/tests/test_seeded_portal_route_smoke.py::test_admin_legal_seeded_registry_smoke` | seeded legal registry returns published documents on canonical admin legal route |
| client dashboard bootstrap | `app/tests/test_seeded_portal_route_smoke.py::test_client_dashboard_seeded_bootstrap_smoke` | seeded owner dashboard resolves canonical widget contract even when deeper read models are absent |
| client logistics reads + trip create + consumption analytics/write | `platform/processing-core/app/tests/test_client_logistics_api.py` + `scripts/smoke_client_logistics.cmd` | seeded client fleet/trips/fuel reads resolve through owner-backed routes, trip create persists order/route/stops with preview-backed snapshot/explain evidence, fuel-consumption analytics reads resolve from persisted fuel links, and fuel-consumption writes return provider-backed sandbox evidence instead of frozen `503` |
| client marketplace browse -> order loop | `platform/processing-core/app/tests/test_client_marketplace_v1.py`, `platform/processing-core/app/tests/test_marketplace_orders_v1.py`, `platform/processing-core/app/tests/test_marketplace_orders_e2e_v1.py`, `platform/processing-core/app/tests/test_marketplace_client_module_gating.py` + `scripts/smoke_marketplace_order_loop.cmd` | seeded marketplace product/offers load on client owner routes, create/pay flow succeeds, partner confirm/proof/complete persists the lifecycle, admin sees the same order timeline, incidents resolve through canonical `cases`, client/admin consequences are mounted `200` item lists, partner settlement stays explicit `409 SETTLEMENT_NOT_FINALIZED` before finalization and returns `200` finalized snapshot/hash/net after admin finalization |
| partner finance dashboard / payouts / audit trail / contracts / settlements | `platform/processing-core/app/tests/test_admin_seed_partner_money.py`, `platform/processing-core/app/tests/test_admin_finance_details.py`, `platform/processing-core/app/tests/test_admin_audit_router.py` + `scripts/smoke_partner_money_e2e.cmd` + `scripts/smoke_partner_settlement_e2e.cmd` | seeded finance-capable partner resolves `portal/me`, dashboard, ledger, payout preview, payout request, admin approve, canonical audit correlation, and read-only contracts/settlements without hidden demo fallback; settlement write/confirm tails remain absent |
| internal notifications delivery | `platform/processing-core/app/tests/test_admin_notifications_router.py`, `platform/processing-core/app/tests/test_notifications_storage_truth.py`, `platform/processing-core/app/tests/test_notifications_invoice_email.py`, `platform/processing-core/app/tests/test_notifications_webhook.py` + `scripts/smoke_notifications_webhook.cmd`, `scripts/smoke_notifications_invoice_email.cmd` | canonical admin notification template/preference/outbox/dispatch routes are runtime-verified, webhook delivery persists as `SENT`, and email flow remains honest `SKIP_OK` when local Mailpit is absent |
| client registration -> activation | `scripts/smoke_onboarding_e2e.cmd` | seeded admin CRM onboarding path now verifies `X-CRM-Version`, lead create/qualify, sequential onboarding actions, and final `FIRST_OPERATION_ALLOWED` state without hidden fallback |

## Readiness gate by phase

| Phase | What must be true |
| --- | --- |
| 0. Defect census | every blocker classified as identity/runtime/fake/state/design gap |
| 1. Canonical accounts | login defaults, seeds, smoke scripts, docs, and auth-host tests use the same seeded matrix |
| 2. P0 runtime blockers | marketplace, cases, geo, legal, client dashboard never show raw backend blobs as primary UI |
| 3. Shared visual reset | gold-primary Dark NEFT Premium tokens own the shared shell; blue is accent only |
| 4. Portal hardening | list/detail pages distinguish first-use, filtered-empty, retry, access-limited |
| 5. Backend/read truth | missing reads are fixed or frozen into explicit compatibility/not-configured states |
| 6. Readiness evidence | route owner, seeded account, expected state, and remaining blockers are documented |

## Strict gate taxonomy

This closeout uses one explicit gate vocabulary:

- `VERIFIED_RUNTIME`: mounted contour has live smoke/runtime proof
- `VERIFIED_PROVIDER_SANDBOX`: external-provider adapter has sandbox-contract proof without production secrets
- `VERIFIED_SKIP_OK`: contour is proven, but a bounded local precondition may honestly return `SKIP_OK`
- `OPTIONAL_NOT_CONFIGURED`: contour is optional in the current internal gate and may stay intentionally disabled/not mounted
- `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE`: contour is deliberately excluded until the provider phase or a future mounted owner wave
- `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER`: host-side suite/env limitation does not override healthy compose runtime plus mounted smoke proof

## External provider phase taxonomy

External provider readiness is now reported separately from internal owner health. Runtime services expose `external_providers` in their health payloads, and the admin runtime summary aggregates those rows without converting provider-degraded states into internal runtime failures.

Provider statuses:

- `DISABLED`: intentionally off in this environment
- `CONFIGURED`: adapter/config exists, but this snapshot is not a live success proof
- `HEALTHY`: configured and usable according to the runtime owner
- `DEGRADED`: required provider config is incomplete or the contour is blocked by provider readiness
- `AUTH_FAILED`: upstream provider credentials/signature/certificate were rejected
- `TIMEOUT`: upstream provider call exceeded its timeout budget
- `UNSUPPORTED`: vendor is not selected or adapter is not wired
- `RATE_LIMITED`: upstream throttling

Current external provider foundation proof:

- `integration-hub /health` reports Diadok, SMTP/email, OTP/SMS, notifications, and webhook intake provider rows.
- `document-service /health` reports neutral `esign_provider` status while preserving the existing Provider X-compatible adapter.
- `logistics-service /health` reports logistics transport and OSRM route-compute provider rows.
- `/api/core/v1/admin/runtime/summary` aggregates provider diagnostics from the mounted services plus processing-core owned bank/ERP/fuel provider blockers.
- Admin Runtime Center renders External Provider Diagnostics as a separate operator panel.

Acceptance rule for this phase:

- concrete selected providers must move to `VERIFIED_PROVIDER_SANDBOX` or `VERIFIED_PROVIDER_PRODUCTION` only after mode, credentials, health proof, and smoke evidence exist
- unknown vendors stay `UNSUPPORTED_PROVIDER_BLOCKER`
- dev/test `mock` can support local workflow evidence, but cannot pass the production gate unless break-glass is explicitly enabled and audited

## Remaining explicit blockers

- backend stability/read-model truth now has missing-table/bootstrap guards for admin moderation, geo, legal list surfaces, and client dashboard; deeper data-population readiness still remains
- seeded smoke now covers admin marketplace, geo, legal registry, client dashboard, and client activation/onboarding owner routes
- compose-gate Linux CI no longer carries placeholder client onboarding/docflow steps: review, approve, generated-doc signing, and client docflow package/notification flows now execute real mounted owner routes
- backend verification gate is now honest instead of blanket-green:
  - full local suites are green for `auth-host` (with DB-dependent slices still explicit `SKIP_OK` when host access to the mapped Postgres auth path is unavailable), `document-service`, and `integration-hub`
  - core-stack verification is green through `scripts/test_core_stack.cmd`
  - `billing-clearing`, `logistics-service`, and `crm-service` still have local host-python dependency blockers for full standalone pytest (`celery` / `fastapi` absent in the host env), so their pre-external evidence remains anchored in live runtime smoke + healthy compose targets instead of a fake “all full suites green” claim
- admin runtime center now reads probe-backed health for auth/gateway/integration/ai plus observability stack components; legacy unmounted diagnostics sidecars were removed instead of being kept as competing weak surfaces
- pricing inner loop now has explicit backend evidence: versioned schedule, marketplace pricing, effective-price resolution, and partner station prices targeted tests are green even though broader portal pricing UX is still partial
- audit/trust layer now has explicit backend evidence: retention, signing health/KMS/Vault, case-event hash-chain/signatures, decision-memory audit linkage, tamper evidence, and trust gates are green in targeted runtime tests
- Analytics/BI is now launch-gated runtime proof: `scripts/compose_launch_gate.cmd` enables ClickHouse without writing secrets to `.env`, sync init/incremental return `200`, and Ops/partner/client/CFO dashboard smokes return `200`; disabled-mode `bi_disabled` remains regression coverage outside the launch gate
- Notifications now have real internal readiness evidence: webhook delivery smoke is green, admin duplicate-template conflicts are explicit `409` instead of raw `500`, and local email remains an honest Mailpit-gated `SKIP_OK`
- live observability proof is now present: compose-level smoke verifies mounted health, metrics, Prometheus targets, and canonical admin runtime summary across gateway/core/auth/integration/ai plus the observability stack
- auth-host compose runtime is healthy again after rebuild/reseed; the earlier `missing_tables:users` state was a verification-side stack drift, not a remaining release blocker
- client portal still contains live dynamic/bridge CSS in `frontends/client-portal/src/index.css`; this now requires owner-aware migration, not blind cleanup
- partner finance dashboard / ledger / payout request flow and read-only `/contracts` / `/settlements*` are runtime-verified end-to-end for the seeded partner; write/approval actions remain admin-owned
- partner portal still needs the same canonical seed vs hidden demo-runtime audit across more pages
- full platform-wide readiness remains phased work, not a single unsafe mega-flip

## Backend verification closeout

Green full local suites:

- `auth-host`: full local suite green; compose runtime health restored; remaining DB-dependent host skips are environment/auth-path limits, not release blockers
- `document-service`: full local suite green
- `integration-hub`: full local suite green

Latest closeout run: `docs/diag/PRE_EXTERNAL_CLOSEOUT_20260421.md`.

Closeout deltas from the latest local runtime pass:

- `processing-core` targeted internal gate passed: `32 passed`
- `auth-host` targeted admin/login gate passed after correcting a stale UUID assertion in the audit test: `11 passed`
- `document-service` and `integration-hub` compose runtime health stayed green, but their runtime images do not include `pytest`; container-side test attempts are classified as `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER`, while full local-suite wording remains tied to a service `.venv`
- all three portals built successfully and passed full `vitest`
- portal Playwright smoke passed for admin/client/partner login
- runtime smokes passed for marketplace order loop, partner money, clearing, reconciliation request/sign, cards, support, and observability
- temporary manual browser probe passed admin user create, client read-only mode indicator, partner product create/submit, and admin moderation visibility

Green internal gate via mounted runtime proof:

- `processing-core`: current core stack plus targeted proofs collected in this readiness wave remain green

`HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` services:

- `billing-clearing`: standalone host pytest still depends on local `celery`; release evidence is grounded in healthy compose runtime plus `scripts/smoke_clearing_batch.cmd`
- `logistics-service`: standalone host pytest still depends on local `fastapi`; release evidence is grounded in healthy compose runtime plus `scripts/smoke_client_logistics.cmd`
- `crm-service`: standalone host pytest still depends on local `fastapi` / `sqlalchemy`; release evidence is grounded in healthy compose runtime plus onboarding/partner smoke coverage

## Pre-External Exclusions

| Contour | Current user-visible behavior | Why excluded | Evidence today | Unlock phase |
| --- | --- | --- | --- | --- |
| Partner contract/settlement write actions | read-only `/contracts` and `/settlements*` are mounted; confirm/approval writes remain absent | money/write semantics stay admin-owned until a dedicated finance workflow exists | `scripts/smoke_partner_settlement_e2e.cmd` | post-launch finance write workflow |
| Client production fuel-provider credentials | sandbox-backed fuel-consumption write returns `200`; production provider credentials remain absent | no real secrets are stored in repo or `.env` by this closeout | `scripts/smoke_client_logistics.cmd`, `docs/diag/client-logistics-fuel-write-live-smoke-20260425.json` | credentialed production provider phase |
| Marketplace recommendations / ads | not accepted as gate-green unless a mounted owner route is actually proven | recommendation/ads contour is not part of the mounted order/consequence/readiness proof set | marketplace order loop smoke proves browse/order/consequence/settlement lifecycle instead | provider/data-owner phase |
| Production OTP/SMS/email providers | sandbox adapters are verified; real delivery credentials are absent | provider-backed production delivery intentionally requires external secrets and vendor accounts | `scripts/smoke_external_provider_sandbox.cmd` | credentialed production provider phase |
| Production EDO transport | Diadok/SBIS sandbox modes are verified; production certificates/tokens are absent | external transport production wiring intentionally remains config-driven | internal documents/docflow and partner docs remain green without production-provider claim | credentialed production provider phase |
| Production bank API / ERP/1C / external fuel-routing | sandbox contract proof is verified; production credentials and destructive sync are absent | external business connector phase intentionally requires selected providers | clearing/reconciliation/logistics internal contours plus sandbox provider proof are present | credentialed production provider phase |

## Final acceptance wording

- all mounted internal owners are verified or honestly degraded under the strict taxonomy above
- all production-provider credentials/write contours remain explicit exclusions after sandbox proof
- no fake parity remains in release-facing readiness wording before credentialed production integrations begin

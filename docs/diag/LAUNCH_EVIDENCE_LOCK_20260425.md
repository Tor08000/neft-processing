# Launch Evidence Lock - 2026-04-25

## Purpose

This file locks the evidence map for the current NEFT full-repo hardening workstream before final PR packaging. It ties completed waves to concrete repo evidence and prevents stale launch claims from drifting ahead of runtime proof.

This is an evidence lock, not a new runtime test result. It records what already exists and how final review slices should classify it.

## Gate Taxonomy

| Status | Meaning |
| --- | --- |
| `VERIFIED_RUNTIME` | mounted contour has live smoke/runtime proof |
| `VERIFIED_PROVIDER_SANDBOX` | external-provider adapter has sandbox-contract proof without production secrets |
| `VERIFIED_SKIP_OK` | contour is proven, but a bounded local precondition may honestly return `SKIP_OK` |
| `OPTIONAL_NOT_CONFIGURED` | optional contour is intentionally disabled/not mounted in the current gate |
| `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` | contour is deliberately excluded until provider or mounted-owner proof exists |
| `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` | host/local test harness gap does not override healthy compose/runtime proof |

## Completed Wave Evidence

| Wave | Locked status | Evidence |
| --- | --- | --- |
| Admin rules sandbox and hidden admin surfaces | `VERIFIED_RUNTIME` / frozen helpers | `docs/admin/ADMIN_PORTAL_TRUTH_MAP.md`, `docs/diag/screenshots/admin-rules-sandbox-ops.png`, `docs/diag/screenshots/admin-rules-sandbox-support-nav.png`, `docs/diag/screenshots/admin-rules-sandbox-observer-nav.png` |
| Admin dashboard/shell, CRM, revenue, support, marketplace moderation | `VERIFIED_RUNTIME` | `docs/diag/admin-dashboard-live-smoke.json`, `docs/diag/admin-revenue-live-smoke.json`, `docs/diag/admin-support-marketplace-live-smoke.json` |
| Client/partner support, cases, marketplace incident linkage | `VERIFIED_RUNTIME` | `docs/client/CLIENT_SUPPORT_CASES_TRUTH_MAP.md`, `docs/partner/PARTNER_PORTAL_TRUTH_MAP.md`, `docs/diag/client-partner-support-marketplace-live-smoke.json`, `docs/diag/screenshots/client-support-inbox.png`, `docs/diag/screenshots/partner-support-inbox.png` |
| Marketplace consequences, credits, settlement readiness | `VERIFIED_RUNTIME` | `docs/diag/marketplace-order-loop-live-smoke-20260425.json`, `scripts/smoke_marketplace_order_loop.cmd`, `platform/processing-core/app/tests/test_marketplace_orders_e2e_v1.py`, `frontends/client-portal/src/pages/MarketplaceOrderDetailsPage.test.tsx`, `frontends/partner-portal/src/pages/OrderDetailsPage.test.tsx` |
| External provider truth | `VERIFIED_PROVIDER_SANDBOX` | `docs/diag/external-provider-sandbox-proof-20260425.json`, `docs/diag/external-provider-truth-live-smoke.json`, `docs/ops/runbooks/external_provider_failures.md`, `platform/integration-hub/neft_integration_hub/tests`, `platform/document-service/app/tests` |
| Partner finance `/contracts` and `/settlements*` | `VERIFIED_RUNTIME` | `docs/diag/partner-finance-mounted-routes-live-smoke-20260425.json`, `scripts/smoke_partner_money_e2e.cmd`, `scripts/smoke_partner_settlement_e2e.cmd`, `frontends/e2e/tests/partner-finance-mounted.spec.ts`, `docs/partner/PARTNER_PORTAL_TRUTH_MAP.md` |
| Logistics write expansion | `VERIFIED_RUNTIME` | `docs/diag/client-logistics-write-expansion-live-smoke-20260425.json`, `docs/diag/client-logistics-fuel-write-live-smoke-20260425.json`, `scripts/smoke_client_logistics.cmd`, `platform/processing-core/app/tests/test_client_logistics_api.py`, `platform/logistics-service/neft_logistics_service/tests` |
| AI/risk/scoring truth | `VERIFIED_RUNTIME` | `docs/diag/ai-risk-scoring-truth-live-smoke-20260425.json`, `docs/architecture/adr/ADR-0010-ai-risk-owner-truth.md`, `platform/processing-core/app/tests/test_decision_memory_audit.py`, `platform/ai-services/risk-scorer/app/tests` |
| BI/analytics truth | `VERIFIED_RUNTIME` | `docs/as-is/BI_ANALYTICS_TRUTH_MAP.md`, `docs/diag/bi-analytics-truth-live-smoke-20260425.json`, `platform/processing-core/app/tests/test_bi_optional_truth.py`, `scripts/smoke_bi_ops_dashboard.cmd`, `scripts/smoke_bi_partner_dashboard.cmd`, `scripts/smoke_bi_client_spend_dashboard.cmd`, `scripts/smoke_bi_cfo_dashboard.cmd` |
| Repo hygiene closeout | `VERIFIED_BY_DOCS` | `docs/diag/REPO_HYGIENE_20260425.md`, `docs/diag/RELEASE_PATCH_SLICES_20260425.md`, `.gitignore` generated-artifact policy |
| S1/S2 owner review closeout | `VERIFIED_BY_TESTS` / `VERIFIED_BY_DOCS` | `docs/diag/S1_S2_OWNER_REVIEW_20260425.md`, `.dockerignore`, `.gitignore`, `gateway/default.conf`, `gateway/nginx.conf`, `platform/processing-core/app/tests/test_hidden_gateway_aliases_topology.py` |
| S3/S4 owner review closeout | `VERIFIED_BY_TESTS` / `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` | `docs/diag/S3_S4_OWNER_REVIEW_20260425.md`, `platform/auth-host/app/tests/test_auth_me.py`, `platform/document-service/app/tests`, `platform/integration-hub/neft_integration_hub/tests`, `platform/logistics-service/neft_logistics_service/tests/test_settings_and_provider_selection.py` |
| S5 admin-ui owner review closeout | `VERIFIED_BY_TESTS` / frozen helpers | `docs/diag/S5_ADMIN_UI_OWNER_REVIEW_20260425.md`, `frontends/admin-ui/src/App.entrypoint.test.tsx`, `frontends/admin-ui/src/admin/AdminShell.test.tsx`, `docs/admin/ADMIN_PORTAL_TRUTH_MAP.md`, `docs/diag/admin-dashboard-live-smoke.json`, `docs/diag/admin-revenue-live-smoke.json`, `docs/diag/admin-support-marketplace-live-smoke.json` |
| S6 client-portal owner review closeout | `VERIFIED_BY_TESTS` / frozen compatibility tails | `docs/diag/S6_CLIENT_PORTAL_OWNER_REVIEW_20260425.md`, `frontends/client-portal/src/pages/ConnectFlowPage.test.tsx`, `frontends/client-portal/src/pages/DashboardPage.test.tsx`, `frontends/client-portal/src/pages/dashboard/DashboardRenderer.documents-links.test.tsx`, `frontends/client-portal/src/App.onboarding-routing.test.tsx` |
| S7 partner-portal owner review closeout | `VERIFIED_BY_TESTS` / mounted finance read tails | `docs/diag/S7_PARTNER_PORTAL_OWNER_REVIEW_20260425.md`, `frontends/partner-portal/src/pages/PartnerDemoRouting.test.tsx`, `frontends/partner-portal/src/pages/Pages.test.tsx`, `frontends/partner-portal/src/AppShell.test.tsx`, `docs/partner/PARTNER_PORTAL_TRUTH_MAP.md`, `frontends/e2e/tests/partner-finance-mounted.spec.ts` |
| S8 shared brand owner review closeout | `VERIFIED_BY_TESTS` / visual-system owner truth | `docs/diag/S8_SHARED_BRAND_OWNER_REVIEW_20260425.md`, `docs/architecture/NEFT_VISUAL_SYSTEM.md`, `frontends/shared/brand/check-brand-imports.js`, `frontends/shared/check-shared-imports.js`, `frontends/shared/brand/components` |
| S9 e2e/browser smoke owner review closeout | `VERIFIED_BY_TESTS` / harness truth | `docs/diag/S9_E2E_BROWSER_SMOKE_OWNER_REVIEW_20260425.md`, `frontends/e2e/playwright.e2e.config.ts`, `frontends/e2e/tests/admin-smoke.spec.ts`, `frontends/e2e/tests/client-smoke.spec.ts`, `frontends/e2e/tests/partner-smoke.spec.ts`, `frontends/e2e/tests/partner-finance-mounted.spec.ts` |
| S11 scripts/smokes owner review closeout | `VERIFIED_BY_SMOKE` / generated-scratch policy | `docs/diag/S11_SCRIPTS_SMOKES_OWNER_REVIEW_20260425.md`, `scripts/seed_partner_money_e2e.cmd`, `scripts/smoke_partner_money_e2e.cmd`, `scripts/smoke_partner_settlement_e2e.cmd`, `scripts/smoke_marketplace_order_loop.cmd` |
| S10 docs/evidence owner review closeout | `VERIFIED_BY_DOCS` / evidence-lock self-check | `docs/diag/S10_DOCS_EVIDENCE_OWNER_REVIEW_20260425.md`, `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md`, `docs/as-is/VERIFY_EVIDENCE_INDEX.md`, `docs/release/PLATFORM_PRODUCTION_READINESS_MATRIX.md`, `docs/as-is/NEFT_PLATFORM_READINESS_MAP.md` |
| S12 ops snapshot owner review closeout | `VERIFIED_BY_DOCS` / local-only snapshot policy | `docs/diag/S12_OPS_SNAPSHOT_OWNER_REVIEW_20260425.md`, `.gitignore`, `.ops/README.md`, `.ops/access.example.ps1` |
| S13 root misc/risky deletions owner review closeout | `VERIFIED_BY_DOCS` / blocker resolved | `docs/diag/S13_ROOT_MISC_RISKY_DELETIONS_REVIEW_20260425.md`, `shared/python/neft_shared/logging_setup.py`, `shared/python/neft_shared/settings.py`, `sitecustomize.py`, `conftest.py`, `pytest.ini` |
| Final pathspec groups | `VERIFIED_BY_DOCS` / no staging performed | `docs/diag/FINAL_PATHSPEC_GROUPS_20260425.md`, `docs/diag/RELEASE_PATCH_SLICES_20260425.md` |

## Explicit Remaining Tails

| Tail | Classification | Locked behavior |
| --- | --- | --- |
| Production EDO/SBIS/Diadok transport | `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` after sandbox proof | sandbox modes are verified without production secrets; production credentials/certificates remain out of repo |
| Production OTP/SMS/email delivery | `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` after sandbox proof | sandbox/idempotency paths are verified; real vendor delivery remains config-driven and secret-free |
| Production bank API and ERP/1C | `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` after sandbox proof | sandbox contract proof is verified; production bank/1C credentials and destructive sync remain outside this closeout |
| Production external fuel/logistics providers | `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` after sandbox proof | sandbox provider path is verified for fuel/logistics calls; production vendor integration remains a later credentialed phase |
| Marketplace recommendations/ads depth | `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE` | order loop, consequences, and settlement readiness are verified; external recommendation/ads providers remain separate |
| Non-critical product-depth enhancements | `VERIFIED_RUNTIME` with known enhancements | portal pricing UX, CRM cross-links, observability drilldowns, and new route browser coverage were kept to critical launch paths; remaining broader UX polish is not a launch blocker |

## Evidence File Policy

Reviewable launch evidence is limited to:

- files referenced in this lock;
- docs indexed from `docs/as-is/VERIFY_EVIDENCE_INDEX.md`;
- runtime maps under `docs/release` and `docs/as-is`;
- screenshots under `docs/diag/screenshots` when referenced by a live visibility matrix.

Non-evidence scratch:

- scripts `_tmp` outputs
- root smoke JSON/TXT files ignored by `.gitignore`
- Playwright test-results and reports
- ad hoc local diagnostics not referenced from this file

## Final Closeout Rule

Final PR closeout must cite this lock and the 2026-04-25 slice map. Any later wave that changes runtime truth must either update this file or create a newer dated evidence lock.

## Packaging Blocker Resolution

S13 root misc/risky deletion review is documented in `docs/diag/S13_ROOT_MISC_RISKY_DELETIONS_REVIEW_20260425.md`.

The former root project-entrypoint docs/config/test harness deletion blocker is closed by restoring these files from `HEAD`; they are no longer deletion candidates:

- `.pre-commit-config.yaml`
- `AGENTS.md`
- `CHANGELOG.md`
- `Makefile`
- `README.md`
- `conftest.py`
- `pytest.ini`
- `docker-compose.dev.yml`
- `docker-compose.smoke.yml`
- `docker-compose.test.yml`

Remaining S13 root helper deletions are reviewable only with the replacement/freeze notes in the S13 document. Ignored root scratch remains outside launch evidence.

# Repo Hygiene Closeout - 2026-04-21

## Scope

This pass separates verified runtime/product work from generated local artifacts and risky dirty-tree state before the external API phase.

Rules used:

- no `git reset`, no checkout restore, no broad deletion;
- generated artifacts may be removed only after resolved paths are verified inside `C:\neft-processing`;
- risky deletions stay untouched until a release owner reviews them;
- repo hygiene is documented separately from product readiness so a clean-looking tree is not mistaken for runtime proof.

## Cleanup Performed

Removed exact generated/local artifacts only:

| Path | Reason |
| --- | --- |
| `frontends/test-results/.last-run.json` | Playwright generated state. |
| `frontends/test-results` | Empty generated test-results directory after file removal. |
| `frontends/login_admin_LOGIN_INPUTS_NOT_FOUND_1776656946636.png` | Local debug screenshot. |
| `generate_invoice.json` | Local scratch JSON. |
| `invoices.json` | Local scratch JSON. |
| `.npm-cache` | Local npm cache, not repository source. |
| `Microsoft` | Accidental PowerShell module analysis cache under repo root. |
| `frontends/client-portal/.vitest-client.json` | Stale generated vitest JSON from an older failed run; current vitest evidence is green in the closeout evidence file. |
| `scripts/_tmp` | Smoke scratch outputs, captured JSON, and temporary sink files. |
| `frontends/ui-audit` | Generated UI crawl screenshots/reports, not source truth. |

Verification after cleanup:

| Check | Result |
| --- | --- |
| `.npm-cache` exists | `False` |
| `Microsoft` exists | `False` |
| `frontends/client-portal/.vitest-client.json` exists | `False` |
| `scripts/_tmp` exists | `False` |
| `frontends/ui-audit` exists | `False` |

## Dirty State After Cleanup

`git status --porcelain` after cleanup and closeout reports:

| Status | Count | Classification |
| --- | ---: | --- |
| `M` | 983 | Large intended/product/docs/test changes plus pre-existing dirty worktree. |
| `D` | 66 | Risky deletions; do not restore or accept automatically. |
| `??` | 220 | Mostly new docs/tests/runtime contours; generated artifacts above were removed. |

Top-level grouping after cleanup:

| Status | Top-level | Count |
| --- | --- | ---: |
| `M` | `platform` | 551 |
| `M` | `frontends` | 291 |
| `M` | `docs` | 66 |
| `M` | `scripts` | 66 |
| `M` | root/config/misc | 9 |
| `??` | `platform` | 109 |
| `??` | `frontends` | 81 |
| `??` | `docs` | 22 |
| `??` | `scripts` | 5 |
| `??` | `.ops` | 1 |
| `??` | `services` | 2 |
| `D` | root/config/misc | 25 |
| `D` | `frontends` | 32 |
| `D` | `platform` | 9 |

## Risky Deletions Requiring Release-Owner Review

These deletions were intentionally left untouched:

| Area | Deleted paths |
| --- | --- |
| Root docs/config/test helpers | `.pre-commit-config.yaml`, `AGENTS.md`, `CHANGELOG.md`, `Makefile`, `README.md`, `conftest.py`, `pytest.ini`, `docker-compose.dev.yml`, `docker-compose.smoke.yml`, `docker-compose.test.yml` |
| Root scripts/scratch | `admin_tests.cmd`, `ai_tests.cmd`, `auth_tests.cmd`, `run_tests.cmd`, `selftest.cmd`, `find_auth_endpoints.py`, `inspect_neft_repo.py`, `tree_to_file.cmd`, `admin_login.json`, `req.json`, `diag_v021.txt`, `structure.txt`, `docs_client_logistics_not_found_report.md`, `curl`, `index.html` |
| Admin UI legacy/support surfaces | `frontends/admin-ui/src/api/health.ts`, `frontends/admin-ui/src/api/integrationMonitoring.ts`, `frontends/admin-ui/src/pages/HealthPage.tsx`, `frontends/admin-ui/src/pages/IntegrationMonitoringPage.tsx`, `frontends/admin-ui/src/pages/IntegrationMonitoringPage.test.tsx`, `frontends/admin-ui/src/pages/SupportRequestsPage.tsx`, `frontends/admin-ui/src/pages/support/CaseDetailsPage.tsx`, `frontends/admin-ui/src/pages/support/CasesListPage.tsx`, `frontends/admin-ui/src/router/index.tsx`, `frontends/admin-ui/src/router/router-shim.tsx`, `frontends/admin-ui/src/types/health.ts` |
| Admin UI decorative/KPI residue | `frontends/admin-ui/src/features/achievements/*`, `frontends/admin-ui/src/features/kpi/*`, `frontends/admin-ui/src/pages/BillingDashboardPage.tsx`, `frontends/admin-ui/src/pages/DashboardPage.tsx`, `frontends/admin-ui/src/pages/ops/OpsDrilldownPlaceholderPage.tsx` |
| Client/partner frozen or replaced pages | `frontends/client-portal/src/pages/ConnectFlowPage.tsx`, `frontends/client-portal/src/components/__snapshots__/EmptyState.test.tsx.snap`, `frontends/partner-portal/src/pages/DocumentDetailsPage.tsx`, `frontends/partner-portal/src/pages/PartnerContractsPage.tsx`, `frontends/partner-portal/src/pages/PayoutBatchesPage.tsx`, `frontends/partner-portal/src/pages/PayoutTracePage.tsx`, `frontends/partner-portal/src/pages/SettlementDetailsPage.tsx` |
| Processing-core legacy/service tails | `platform/processing-core/app/api/v1/endpoints/admin_clearing.py`, `platform/processing-core/app/routers/admin_me_legacy.py`, `platform/processing-core/app/routers/admin_runtime_legacy.py`, `platform/processing-core/services/audit_log.py`, `platform/processing-core/services/billing.py`, `platform/processing-core/services/clearing.py`, `platform/processing-core/services/pricing.py`, `platform/processing-core/services/risk_adapter.py`, `platform/processing-core/services/rules_engine.py` |

Review policy:

- accept a deletion only when the replacement route/owner is verified and docs already mark the old surface frozen or retired;
- restore nothing automatically from git because the repository baseline is known to be stale;
- if a deleted root helper is still referenced by docs/CI/local workflows, either reintroduce a safe current version or update the reference.

## Release Patch Inventory

Likely intended release patch areas:

| Area | Evidence |
| --- | --- |
| `platform/processing-core` | Partner onboarding, support/cases, marketplace order loop, client logistics freeze, admin/runtime, finance/clearing/reconciliation, smoke/test harness additions. |
| `platform/auth-host` | Admin user audit/schema/topology/login claim tests; stale UUID assertion fixed and targeted suite green. |
| `platform/document-service` and `platform/integration-hub` | Settings/provider/default tests and integration-hub DB/EDO test scaffolding; runtime images are healthy but host-side container pytest is a harness exception because pytest is not installed in those images. |
| `platform/logistics-service` | Preview compute/schema/provider selection additions aligned with ADR-0003. |
| `platform/crm-service` | Metrics compatibility and migration guard additions; service health green in compose. |
| `frontends/admin-ui` | Operator completion tests/pages for runtime, cases, finance, legal, CRM/commercial, logistics, moderation, and no-raw-payload copy checks. |
| `frontends/client-portal` | Workspace gating, client kind from `portal/me`, canonical cases/docs/finance/marketplace/logistics read states, and error/frozen route tests. |
| `frontends/partner-portal` | Workspace/capabilities shell, partner onboarding owner route, support actions, profile workspace, frozen contracts/settlements handling. |
| `frontends/shared/brand` | Shared visual/state components and tokens. |
| `docs` | ADRs, truth maps, readiness matrices, evidence indexes, runbooks, and final pre-external exclusion taxonomy. |
| `scripts` | Smoke scripts and ops helpers used for marketplace, observability, billing/commerce unblock, and provider/exclusion evidence. |

New untracked items that appear intentional and were left in place:

- `.ops` access/snapshot skeleton;
- `docs/architecture/adr/ADR-0003` through `ADR-0011`;
- `docs/admin/ADMIN_PORTAL_TRUTH_MAP.md`;
- `docs/partner/`;
- `docs/release/PLATFORM_PRODUCTION_READINESS_MATRIX.md`;
- `docs/ops/runbooks/*`;
- `frontends/docker`;
- `services/admin-web`;
- `services/auth-host`.

## Runtime Evidence Reminder

This hygiene pass did not replace runtime verification. The companion closeout evidence is in `docs/diag/PRE_EXTERNAL_CLOSEOUT_20260421.md`.

Reviewable release slices are documented in `docs/diag/RELEASE_PATCH_SLICES_20260421.md`.

Current runtime status after cleanup:

- `docker compose ps`: stack is up; core-api, auth-host, gateway, integration-hub, logistics-service, crm-service, document-service, ai-service, and backing services are healthy where health checks exist.
- Previous closeout evidence remains valid for targeted backend tests, frontend build/vitest, portal smoke, manual browser product flow, marketplace order loop, partner money, clearing, reconciliation, cards, support, and observability smoke.

## Next Gate

Before staging or release packaging:

1. review the 66 deletions with owners and decide which are intentional retirements;
2. review the 1,269 remaining dirty entries by the slice map instead of one monolithic patch;
3. keep generated artifacts ignored/clean so fresh test evidence does not pollute the product diff;
4. keep provider-backed and unmounted contours as explicit exclusions until the external API phase reopens them with provider proof.

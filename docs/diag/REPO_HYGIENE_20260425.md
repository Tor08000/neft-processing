# Repo Hygiene Closeout - 2026-04-25

## Scope

This closeout supersedes the 2026-04-21 hygiene snapshot for review planning only. It does not replace the historical evidence in `docs/diag/REPO_HYGIENE_20260421.md` or `docs/diag/RELEASE_PATCH_SLICES_20260421.md`.

Rules used for this pass:

- no staging, commits, branch split, or patch bundles;
- no `git add .`;
- no restore/reset of dirty paths because the branch baseline is intentionally stale after multiple truth waves;
- no deletion is accepted just because a build or smoke passed;
- generated scratch is excluded from review slices unless it is moved under `docs/diag` and referenced by the evidence lock;
- launch evidence is locked in docs before any final PR packaging.

## Dirty State Snapshot

Snapshot command set:

- `git status --porcelain=v1`
- `git diff --shortstat`
- owner-slice grouping over the same porcelain output

Captured state before applying the generated-artifact ignore policy:

| Status | Count | Meaning |
| --- | ---: | --- |
| `M` | 1105 | tracked modifications across product, tests, docs, scripts, and config |
| `D` | 85 | deletions requiring owner review |
| `??` | 310 | new source/docs/evidence plus local generated artifacts |

Tracked diff footprint:

| Metric | Value |
| --- | ---: |
| changed tracked files | 1207 |
| insertions | 81208 |
| deletions | 50673 |

Current review-visible state after the generated-artifact ignore policy:

| Status | Count | Meaning |
| --- | ---: | --- |
| `M` | 1122 | tracked modifications now include S9 Playwright harness import cleanup plus owner-review docs |
| `D` | 75 | remaining deletions after S13 root entrypoint/harness restore |
| `??` | 283 | untracked generated scratch removed from review-visible status, including closeout evidence |

Generated/local artifacts mixed into the raw status:

| Artifact family | Count | Policy |
| --- | ---: | --- |
| `scripts/_tmp/*` | 17 | generated smoke scratch, excluded from review slices |
| root smoke JSON/TXT outputs | 33 | generated local probes, excluded unless moved to `docs/diag` |
| `frontends/**/test-results/*` | present | generated Playwright state, excluded |
| `docs/diag/*.json` and `docs/diag/screenshots/*` | present | real launch evidence when referenced by the evidence lock |

## Owner Slice Totals Before Ignore Policy

| Slice | Total | `M` | `D` | `??` | Review owner |
| --- | ---: | ---: | ---: | ---: | --- |
| S1 root/gateway/infra | 2 | 2 | 0 | 0 | repo infra / gateway |
| S1 service wrappers | 2 | 0 | 0 | 2 | repo infra / compose wrappers |
| S2 processing-core | 636 | 514 | 9 | 113 | core domain owners |
| S3 auth-host | 28 | 25 | 0 | 3 | identity owner |
| S4 satellite/backend services | 87 | 68 | 0 | 19 | document, integration, logistics, CRM, AI, billing services |
| S5 admin-ui | 198 | 121 | 30 | 47 | admin portal owner |
| S6 client-portal | 154 | 120 | 8 | 26 | client portal owner |
| S7 partner-portal | 92 | 72 | 13 | 7 | partner portal owner |
| S8 shared brand | 17 | 12 | 0 | 5 | shared design system owner |
| S9 e2e/browser smoke | 10 | 6 | 0 | 4 | browser smoke owner |
| S10 docs/evidence | 109 | 74 | 0 | 35 | release/docs owner |
| S11 scripts/smokes | 96 | 82 | 0 | 14 | runtime smoke owner |
| S12 ops snapshot | 1 | 0 | 0 | 1 | ops snapshot owner |
| S13 root misc/generated | 69 | 9 | 25 | 35 | release captain / hygiene owner |

## Review-Visible Owner Slice Totals

| Slice | Total | `M` | `D` | `??` | Review owner |
| --- | ---: | ---: | ---: | ---: | --- |
| S1 root/gateway/infra | 7 | 7 | 0 | 0 | repo infra / gateway |
| S2 processing-core | 636 | 514 | 9 | 113 | core domain owners |
| S3 auth-host | 28 | 25 | 0 | 3 | identity owner |
| S4 satellite/backend services | 87 | 68 | 0 | 19 | document, integration, logistics, CRM, AI, billing services |
| S5 admin-ui | 198 | 121 | 30 | 47 | admin portal owner |
| S6 client-portal | 154 | 120 | 8 | 26 | client portal owner |
| S7 partner-portal | 92 | 72 | 13 | 7 | partner portal owner |
| S8 shared brand | 17 | 12 | 0 | 5 | shared design system owner |
| S9 e2e/browser smoke | 25 | 22 | 0 | 3 | browser smoke owner |
| S10 docs/evidence | 120 | 75 | 0 | 45 | release/docs owner |
| S11 scripts/smokes | 95 | 82 | 0 | 13 | runtime smoke owner |
| S12 ops snapshot | 1 | 0 | 0 | 1 | ops snapshot owner |
| S13 root misc/generated | 18 | 3 | 15 | 0 | release captain / hygiene owner |

## Generated Artifact Policy

Allowed launch evidence locations:

- `docs/diag/*.json`
- `docs/diag/screenshots/*`
- dated closeout docs under `docs/diag`
- truth maps under `docs/as-is`, `docs/admin`, `docs/client`, `docs/partner`, `docs/release`

Excluded generated scratch:

- `scripts/_tmp/*`
- `frontends/**/test-results/*`
- `frontends/**/playwright-report/*`
- root smoke JSON/TXT outputs listed in `.gitignore`
- ad hoc root diagnostic text such as `diag_v*.txt` and `structure.txt`

Policy:

- do not delete generated files as part of owner-slice review;
- do not stage ignored generated files;
- if a smoke output is release evidence, move/capture it under `docs/diag` and add it to `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md`;
- do not add blanket `*.json` or `*.png` ignores because docs evidence uses those extensions.

## Risky Deletions Requiring Owner Review

These 75 deletions are not globally accepted by hygiene docs. S2, S5, S6, S7, and S13 classify their own deletion candidates; final packaging must include each deletion only with that owner-slice replacement/freeze evidence. The former S13 root project-entrypoint deletion blocker is closed by restoring those files from `HEAD`.

Restored root docs/config/test helpers, no longer deletion candidates:

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

Remaining root local helpers and scratch deletion candidates:

- `admin_login.json`
- `admin_tests.cmd`
- `ai_tests.cmd`
- `auth_tests.cmd`
- `curl`
- `diag_v021.txt`
- `docs_client_logistics_not_found_report.md`
- `find_auth_endpoints.py`
- `index.html`
- `inspect_neft_repo.py`
- `req.json`
- `run_tests.cmd`
- `selftest.cmd`
- `structure.txt`
- `tree_to_file.cmd`

Admin UI retired or replacement-candidate surfaces:

- `frontends/admin-ui/src/api/health.ts`
- `frontends/admin-ui/src/api/integrationMonitoring.ts`
- `frontends/admin-ui/src/api/stubs.ts`
- `frontends/admin-ui/src/components/Layout/Layout.tsx`
- `frontends/admin-ui/src/features/achievements/api.ts`
- `frontends/admin-ui/src/features/achievements/components/AchievementBadge.tsx`
- `frontends/admin-ui/src/features/achievements/components/StreakWidget.tsx`
- `frontends/admin-ui/src/features/achievements/types.ts`
- `frontends/admin-ui/src/features/achievements/useAchievements.ts`
- `frontends/admin-ui/src/features/kpi/api.ts`
- `frontends/admin-ui/src/features/kpi/components/KpiCard.tsx`
- `frontends/admin-ui/src/features/kpi/components/KpiHintList.tsx`
- `frontends/admin-ui/src/features/kpi/formatters.ts`
- `frontends/admin-ui/src/features/kpi/types.ts`
- `frontends/admin-ui/src/features/kpi/useKpis.ts`
- `frontends/admin-ui/src/pages/BillingDashboardPage.tsx`
- `frontends/admin-ui/src/pages/DashboardPage.tsx`
- `frontends/admin-ui/src/pages/HealthPage.tsx`
- `frontends/admin-ui/src/pages/IntegrationMonitoringPage.test.tsx`
- `frontends/admin-ui/src/pages/IntegrationMonitoringPage.tsx`
- `frontends/admin-ui/src/pages/SupportRequestsPage.tsx`
- `frontends/admin-ui/src/pages/admin/ComingSoonPage.tsx`
- `frontends/admin-ui/src/pages/ops/OpsDrilldownPlaceholderPage.tsx`
- `frontends/admin-ui/src/pages/stubs/StubProvidersPage.tsx`
- `frontends/admin-ui/src/pages/support/CaseDetailsPage.tsx`
- `frontends/admin-ui/src/pages/support/CasesListPage.tsx`
- `frontends/admin-ui/src/router/index.tsx`
- `frontends/admin-ui/src/router/router-shim.tsx`
- `frontends/admin-ui/src/types/health.ts`
- `frontends/admin-ui/src/types/stubs.ts`

Client portal retired or replacement-candidate surfaces:

- `frontends/client-portal/src/components/__snapshots__/EmptyState.test.tsx.snap`
- `frontends/client-portal/src/components/overview/HeroSummaryCard.tsx`
- `frontends/client-portal/src/components/overview/OperationRow.tsx`
- `frontends/client-portal/src/components/overview/OverviewEmptyState.tsx`
- `frontends/client-portal/src/components/overview/VehicleCard.tsx`
- `frontends/client-portal/src/pages/ConnectFlowPage.tsx`
- `frontends/client-portal/src/pages/OverviewPage.tsx`
- `frontends/client-portal/src/pages/overview.css`

Partner portal retired demo/frozen surfaces:

- `frontends/partner-portal/src/components/DemoEmptyState.tsx`
- `frontends/partner-portal/src/demo/partnerDemoData.ts`
- `frontends/partner-portal/src/pages/DocumentDetailsPage.tsx`
- `frontends/partner-portal/src/pages/PartnerContractsPage.tsx`
- `frontends/partner-portal/src/pages/PayoutBatchesPage.tsx`
- `frontends/partner-portal/src/pages/PayoutTracePage.tsx`
- `frontends/partner-portal/src/pages/SettlementDetailsPage.tsx`
- `frontends/partner-portal/src/pages/analytics/AnalyticsPageDemo.tsx`
- `frontends/partner-portal/src/pages/documents/DocumentsPageDemo.tsx`
- `frontends/partner-portal/src/pages/finance/FinancePageDemo.tsx`
- `frontends/partner-portal/src/pages/orders/OrdersPageDemo.tsx`
- `frontends/partner-portal/src/pages/payouts/PayoutsPageDemo.tsx`
- `frontends/partner-portal/src/pages/services/ServicesCatalogPageDemo.tsx`

Processing-core legacy tails and service residues:

- `platform/processing-core/app/api/v1/endpoints/admin_clearing.py`
- `platform/processing-core/app/routers/admin_me_legacy.py`
- `platform/processing-core/app/routers/admin_runtime_legacy.py`
- `platform/processing-core/services/audit_log.py`
- `platform/processing-core/services/billing.py`
- `platform/processing-core/services/clearing.py`
- `platform/processing-core/services/pricing.py`
- `platform/processing-core/services/risk_adapter.py`
- `platform/processing-core/services/rules_engine.py`

Review rule:

- accept a deletion only when a mounted owner, compatibility freeze, or explicit docs retirement already exists;
- if a deleted helper is still referenced by docs, CI, smoke scripts, or local runbooks, restore or replace it in the same owner slice;
- do not mix deletion acceptance with generated-artifact cleanup.

## Closeout State

The worktree is now split conceptually, not staged physically. S1/S2, S3/S4, S5, S6, S7, S8, S9, S11, S10, S12, and S13 have dated owner-review closeout docs. The S13 root project-entrypoint deletion blocker is closed by restoring the files from `HEAD`. Final PR packaging must use `docs/diag/RELEASE_PATCH_SLICES_20260425.md` as the pathspec map and `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md` as the evidence map.

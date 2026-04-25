# Release Patch Slices - 2026-04-25

## Purpose

The branch contains one large cross-repo hardening workstream. This file defines owner-reviewable slices so final PR closeout can be reviewed without accepting unrelated paths, generated artifacts, or risky deletions by accident.

Rules:

- do not run `git add .`;
- review/stage by explicit pathspecs only;
- keep generated scratch out of review slices;
- review backend/runtime owners before portal/docs claims;
- risky deletions are accepted only with owner confirmation and replacement/freeze evidence.

## Review Order

1. S1 root/gateway/service wrappers
2. S2 processing-core
3. S3 auth-host
4. S4 satellite/backend services
5. S5 admin-ui
6. S6 client-portal
7. S7 partner-portal
8. S8 shared brand
9. S9 e2e/browser smoke
10. S11 scripts/smokes
11. S10 docs/evidence
12. S12 ops snapshot
13. S13 root misc/generated/risky deletions

Reason: runtime and owner contracts must be stable before UI claims, smoke orchestration, and final evidence wording are reviewed.

## Slice Inventory

| Slice | Count | Pathspec scope | Review intent | Required checks |
| --- | ---: | --- | --- | --- |
| S1 root/gateway/infra | 7 | `.dockerignore`, `.gitignore`, `.env`, `.env.example`, `docker-compose.yml`, `gateway/**` | Compose/gateway/runtime wrapper truth without public route drift | `docker compose config --quiet`, `docker compose exec -T gateway nginx -t`, targeted gateway/core/admin smoke if gateway files change |
| S2 processing-core | 636 | `platform/processing-core/**` | Core owner truth for admin, client, partner, finance, marketplace, logistics, AI/risk, BI, documents, cases | targeted pytest for touched domains, smoke scripts named in evidence lock |
| S3 auth-host | 28 | `platform/auth-host/**` | Identity, seeded users, claims, admin-user auth truth | auth-host targeted pytest, login smoke through gateway |
| S4 satellite/backend services | 87 | `platform/document-service/**`, `platform/integration-hub/**`, `platform/logistics-service/**`, `platform/crm-service/**`, `platform/ai-services/**`, `platform/billing-clearing/**` | Provider truth, transport ownership, explicit degraded modes, service harness boundaries | service pytest where available, service `/health`, provider/degraded evidence |
| S5 admin-ui | 198 | `frontends/admin-ui/**` | Operator console truth, RBAC/capability visibility, mounted-or-frozen surfaces | targeted Vitest for touched pages, admin build, live role matrix when route visibility changes |
| S6 client-portal | 154 | `frontends/client-portal/**` | Client product truth, canonical reads, marketplace/logistics/support/docs states | targeted Vitest for touched pages, client build, relevant client smoke |
| S7 partner-portal | 92 | `frontends/partner-portal/**` | Partner kind/capability truth, mounted finance read tails, support/order/workspace states | targeted Vitest for touched pages, partner build, partner money/settlement route smoke |
| S8 shared brand | 17 | `frontends/shared/**`, `brand/**` | Shared visual/state system consistency across portals | affected portal builds or focused visual shell tests |
| S9 e2e/browser smoke | 25 | `frontends/e2e/**` | Browser smoke truth without generated test-results | Playwright smoke for changed specs, no `test-results` staging |
| S10 docs/evidence | 120 | `docs/**` | Truth maps, readiness matrices, ADRs, runbooks, evidence lock | path existence check, JSON evidence validation, docs diff check |
| S11 scripts/smokes | 95 | `scripts/**` excluding generated scratch | Runtime smoke entrypoints and seed helpers | run touched smoke scripts or classify as SKIP_OK/blocked in docs |
| S12 ops snapshot | 1 | `.ops/**` | Ops snapshot skeleton, if intentionally retained | owner review; do not stage private/operator data |
| S13 root misc/generated | 18 | root files not covered above | Risky deletions, root helpers, remaining untracked root files, release captain cleanup | reference scan before accepting deletions; no generated scratch staging |

## Slice Guardrails

S1:

- `.env` is local verification only and must not be staged for release unless explicitly approved.
- service-wrapper `.env` files are local scratch and ignored; they are not S1 review artifacts.
- Gateway public families must not change without route topology docs and sentinel evidence.

S2:

- No money formulas, settlement math, auth semantics, or public API removals are accepted in a hygiene-only review.
- Compatibility tails remain frozen unless the owning domain slice carries tests and docs for the change.

S3:

- Login, token, and seeded-user semantics must remain compatible with existing smoke scripts.
- No hidden broadening of admin/user permissions.

S4:

- Provider adapters must fail explicitly as `DEGRADED`, `UNSUPPORTED`, `AUTH_FAILED`, `TIMEOUT`, or local `SKIP_OK`; no silent fallback.
- Harness exceptions are docs classifications, not fake test passes.

S5-S7:

- A page is accepted only when mounted with capability/state truth or explicitly frozen/removed.
- No raw backend payloads as primary UI.
- No demo fallback on normal production routes.

S8:

- Shared tokens/components must not create one-portal-only regressions.
- Portal-specific styling stays in portal slices unless promoted intentionally.

S9-S11:

- Generated smoke output stays under ignored scratch directories.
- Release evidence must be captured in `docs/diag` and referenced from the evidence lock.

S12-S13:

- Root helper deletions require reference checks in docs, scripts, CI, and runbooks.
- Generated local outputs are not proof unless promoted into `docs/diag`.

## Remaining Explicit Tails

The following are intentionally not production-green in this slice plan after the seven-tail closeout:

- Partner contract/settlement write actions: read-only surfaces are mounted; write/approval tails remain admin-owned.
- Marketplace recommendations/ads: order loop, consequences, and settlement readiness are verified; external recommendations stay separate.
- Production EDO, OTP/SMS/email, bank API, ERP/1C, external fuel/logistics providers: sandbox proof exists; production credentials/certificates remain out of repo.
- Non-critical product-depth enhancements: critical UX is launch-ready; broader polish stays as non-launch backlog.

## Final Packaging Rule

Final staging should use these slices as pathspec groups. A slice is reviewable only when its required checks and referenced evidence are present; otherwise it remains dirty but classified.

## S1/S2 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S1_S2_OWNER_REVIEW_20260425.md`.

S1 is reviewable with one guard: `.env` remains a tracked local verification file and must not be staged as a release artifact. `.dockerignore` now excludes `.env` from Docker build context, and `.gitignore` excludes service-wrapper `.env` files plus generated smoke scratch.

S2 is reviewable as a core-owner slice: targeted runtime pytest, route/capability sentinels, and container compileall passed. The 9 processing-core deletion candidates are not accepted by this document globally; they have owner-review evidence and can be accepted only inside S2 staging if the reviewer intentionally includes those paths.

## S3/S4 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S3_S4_OWNER_REVIEW_20260425.md`.

S3 is reviewable after fixing a stale `test_auth_me.py` key-service patch target. Auth-host targeted suite passed from the service `.venv` on current workspace code; the running container still had stale image code and is not used as the post-fix test source until rebuild.

S4 is reviewable with explicit harness boundaries: document-service and integration-hub full service suites passed; logistics pure provider/idempotency tests and compileall passed; CRM/AI/billing compileall passed; live health endpoints for AI/document/integration/logistics/CRM returned `200` with provider diagnostics staying explicit.

## S5 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S5_ADMIN_UI_OWNER_REVIEW_20260425.md`.

S5 is reviewable as an admin-portal owner slice. The 30 deleted admin-ui files are replacement/freeze-reviewed, not globally accepted: legacy router/layout, fake dashboard/KPI/achievements, support duplicates, stub provider UI, health/integration sidecars, and placeholder pages are replaced by canonical `App.tsx`, `AdminShell`, `/runtime`, `/cases*`, `/finance*`, `/marketplace/moderation*`, `/rules/sandbox`, `/risk/rules*`, `/policies*`, and route sentinels. Full admin-ui Vitest and production build passed.

## S6 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S6_CLIENT_PORTAL_OWNER_REVIEW_20260425.md`.

S6 is reviewable as a client-portal owner slice. The 8 deleted client files are replacement/freeze-reviewed, not globally accepted: old overview components/page/CSS are replaced by canonical `DashboardPage`, `DashboardRenderer`, current layout/shared brand owners, and dashboard state tests; `ConnectFlowPage` is frozen as `/connect*` compatibility redirects into canonical `/onboarding*`; the removed `EmptyState` snapshot is replaced by rendered DOM assertions. Full client-portal Vitest and production build passed.

## S7 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S7_PARTNER_PORTAL_OWNER_REVIEW_20260425.md`.

S7 is reviewable as a partner-portal owner slice. The 13 deleted partner files are replacement/freeze-reviewed, not globally accepted: demo data/pages and `DemoEmptyState` are removed because wrappers always render prod surfaces; unmounted document-detail and payout helper pages stay removed; `/contracts` and `/settlements*` are now mounted read-only behind finance workspace/capability truth, while write actions stay absent. Full partner-portal Vitest and production build passed.

## S8 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S8_SHARED_BRAND_OWNER_REVIEW_20260425.md`.

S8 is reviewable as a shared visual-system owner slice. There are no deleted files in the slice. Shared brand/token/component changes are backed by admin, client, and partner import guards plus the already-passed S5/S6/S7 portal production builds.

## S9 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S9_E2E_BROWSER_SMOKE_OWNER_REVIEW_20260425.md`.

S9 is reviewable as an e2e/browser-smoke owner slice. There are no deleted files in the slice. A duplicate Playwright runner harness blocker was fixed by aligning all e2e imports/config to local `playwright/test`; generated `test-results` remain ignored; targeted admin/client/partner/partner-finance Playwright smokes pass after the documented `seed_partner_money_e2e` prerequisite.

## S11 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S11_SCRIPTS_SMOKES_OWNER_REVIEW_20260425.md`.

S11 is reviewable as a scripts/smokes owner slice. There are no deleted files in the slice. Generated `scripts/_tmp/*` remains excluded; review-sensitive partner finance and marketplace smoke scripts passed; broader script families remain tied to the launch evidence lock and must be staged by explicit pathspecs.

## S10 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S10_DOCS_EVIDENCE_OWNER_REVIEW_20260425.md`.

S10 is reviewable as a docs/evidence owner slice. There are no deleted files in the slice. The evidence lock references only existing launch-evidence paths, all `docs/diag/*.json` evidence files parse, generated scratch remains excluded, and docs diff hygiene passed.

## S12 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S12_OPS_SNAPSHOT_OWNER_REVIEW_20260425.md`.

S12 is reviewable only as an ops-template skeleton. `.ops/README.md` and `.ops/access.example.ps1` are local setup templates with no secrets; `.ops/snapshots/*`, real kubeconfigs, and real access scripts stay ignored/local-only and are not launch evidence.

## S13 Owner Review Result - 2026-04-25

Evidence: `docs/diag/S13_ROOT_MISC_RISKY_DELETIONS_REVIEW_20260425.md`.

S13 is reviewable as a root misc/generated owner slice. Root project-entrypoint docs/config/test harness files were restored from `HEAD` and no longer appear as deletion candidates. The remaining helper/scratch deletions have replacement/freeze notes; modified shared/bootstrap and host fuel replay harness files passed scoped compile/test or import-skip checks. Final packaging must still stage S13 by explicit pathspecs and must not include ignored root scratch.

## Final Pathspec Groups - 2026-04-25

Evidence: `docs/diag/FINAL_PATHSPEC_GROUPS_20260425.md`.

Final owner-slice pathspec groups are collected without staging. They explicitly exclude `.env`, generated smoke scratch, Playwright reports/results, `.ops/snapshots/*`, real ops access files, and root scratch.

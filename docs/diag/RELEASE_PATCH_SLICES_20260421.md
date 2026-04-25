# Release Patch Slices - 2026-04-21

## Purpose

The repository is runtime-green enough for the internal gate, but the working tree is too large to review or stage safely as one patch. This file splits the remaining dirty state into owner-reviewable slices before the external API phase.

Rules:

- do not run `git add .`;
- do not restore from git automatically because the baseline is stale;
- do not accept deletions only because builds pass;
- review slices in dependency order: backend owners first, then portals, then docs/smoke;
- keep provider-backed and unmounted contours as explicit exclusions until provider proof exists.

## Current Dirty State

After generated-artifact cleanup and closeout docs:

| Status | Count |
| --- | ---: |
| `M` | 983 |
| `D` | 66 |
| `??` | 219 |

Tracked diff footprint:

| Metric | Value |
| --- | ---: |
| changed tracked files | 1049 |
| insertions | 74428 |
| deletions | 44629 |

Deletion reference check:

| Check | Result |
| --- | --- |
| fixed-string current-tree refs for each of the 66 deleted paths | `0` path refs / `0` basename refs |

Interpretation: the deletions are not currently referenced by source/docs after this branch's changes, but root helpers and topology files still require owner review before accepting them.

## Slice Inventory

| Slice | Scope | Status counts | Review intent |
| --- | --- | --- | --- |
| S0 | Closeout evidence docs | `?? 2` | Keep with release evidence. |
| S1 | Root infra/config, brand, service wrappers | `M 7`, `?? 3` | Review carefully for env/compose/gateway/portal runtime boot behavior. |
| S2 | `processing-core` owners | `M 474`, `D 9`, `?? 93` | Primary backend owner slice: partner onboarding, support/cases, marketplace, finance, logistics freeze, runtime/admin, migrations/tests. |
| S3 | `auth-host` | `M 23`, `?? 3` | Auth/admin-user tests and claims alignment; no auth/JWT semantic drift beyond verified fixes. |
| S4 | Satellite services | `M 46`, `?? 13` | Document, integration-hub, logistics, CRM service guards/tests; classify host pytest gaps as harness exceptions only with health proof. |
| S5 | Admin portal | `M 107`, `D 25`, `?? 45` | Operator completion and retired fake/legacy admin surfaces. |
| S6 | Client portal | `M 99`, `D 2`, `?? 24` | Client workspace-from-portal state, canonical cases/docs/finance/marketplace/logistics read states, no manual kind switch. |
| S7 | Partner portal | `M 69`, `D 5`, `?? 7` | Workspace/capabilities shell, onboarding, support, finance read, frozen contracts/settlements behavior. |
| S8 | Shared brand/state components | `M 11`, `?? 4` | Shared visual/state components and tokens used by portals. |
| S9 | Browser smoke / Playwright | `M 5` | Login/product smoke coverage for admin/client/partner. |
| S10 | Readiness/docs | `M 66`, `?? 19` | ADRs, truth maps, matrices, runbooks, exclusion taxonomy. |
| S11 | Scripts/smoke/ops | `M 66`, `?? 5` | Runtime smoke scripts and ops helpers; keep generated outputs out. |
| S12 | `.ops` snapshot skeleton | `?? 1` | Intentional ops access/snapshot scaffold; review separately from product code. |
| S13 | Root deletions/misc plus gateway/AI scorer | `M 10`, `D 25` | Split into gateway/AI runtime changes and risky root helper deletions. |

## Recommended Review Order

1. S1 root infra/config
2. S2 processing-core owners
3. S3 auth-host
4. S4 satellite services
5. S5 admin portal
6. S6 client portal
7. S7 partner portal
8. S8 shared brand
9. S9 browser smoke
10. S11 scripts/smoke
11. S10 readiness/docs
12. S0 closeout evidence
13. S12 ops snapshot
14. S13 risky root deletions/misc

Reason: runtime owner contracts must be reviewed before UI and docs, while risky deletions should be accepted only after replacement paths are confirmed.

## Slice Details And Verification

### S1 Root Infra / Config

Paths:

- `.dockerignore`
- `.env`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `sitecustomize.py`
- `brand/v1/neft-client/tokens.client.css`
- `frontends/docker`
- `services/admin-web`
- `services/auth-host`

Required checks:

- `docker compose ps`
- `docker compose up -d --build core-api auth-host gateway admin-web client-web partner-web`
- `cmd /c scripts\seed.cmd`
- `cmd /c scripts\seed_partner_money_e2e.cmd`

Review notes:

- do not commit real secrets from `.env`;
- confirm compose changes do not remove required dev/test service families;
- keep gateway route families stable.

S1 review result on 2026-04-21:

| Check | Result | Notes |
| --- | --- | --- |
| `git diff --check` for S1 paths | PASS | No whitespace/conflict-marker issues. |
| `.env` / `.env.example` secret scan | REVIEW | Values are local/demo defaults (`change-me`, `Neft123!`, `Client123!`, `Partner123!`, Mailpit/mock providers). Do not stage `.env` for non-local release without owner approval. |
| `docker compose config --quiet` | PASS | Compose config validates; Docker client printed Windows config-file access warnings only. |
| `docker compose exec -T gateway nginx -t` | PASS | Syntax OK; existing duplicate `js/css` type warnings remain non-blocking. |
| `GET http://localhost/health` | PASS | Gateway returned `200 OK`. |
| `POST /api/v1/auth/login` with `portal=admin` then `GET /api/v1/admin/users` | PASS | Existing `auth-host` admin-users owner is reachable through gateway; probe returned admin roles and user list. |

S1 follow-up applied:

- aligned `gateway/nginx.conf` with runtime-used `gateway/default.conf` for exact `/api/auth`, so both gateway configs now use the same no-redirect alias behavior.

S1 risk notes:

- `gateway/default.conf` is the runtime config copied by `gateway/Dockerfile`; `gateway/nginx.conf` is still kept aligned to avoid stale contract drift.
- `/api/v1/admin/users` and `/api/auth/v1/admin/users` are gateway exposure of the existing `auth-host` admin-users route, not a new processing-core business owner.
- `.env` remains a local verification file with demo credentials; release packaging should prefer `.env.example` or secret-store values.

### S2 Processing-Core Owners

Main contour groups:

- partner onboarding owner and tests;
- support/cases canonical owner and support-request bridge;
- marketplace order loop and client marketplace state;
- client logistics provider-backed fuel-consumption write tail;
- admin runtime, admin audit, admin portal access;
- finance/clearing/reconciliation/card/support smoke-backed flows;
- migrations for additive runtime repairs.

Targeted verification already captured:

- core targeted pytest: `32 passed`;
- marketplace order loop smoke: PASS;
- partner money smoke: PASS;
- clearing smoke: PASS;
- reconciliation request sign smoke: PASS;
- cards issue smoke: PASS;
- support ticket smoke: PASS;
- observability smoke: PASS.

Before staging S2, rerun the targeted core pytest if backend files move again.

### S3 Auth-Host

Main contour groups:

- admin user audit/schema/topology tests;
- login portal claims tests;
- stale UUID assertion fixed in `test_admin_users_audit.py`.

Targeted verification already captured:

- auth-host targeted pytest: `11 passed`;
- auth-host compose health: healthy.

Guardrail:

- no auth/JWT/session semantic expansion in this slice.

### S4 Satellite Services

Scopes:

- `platform/document-service`
- `platform/integration-hub`
- `platform/logistics-service`
- `platform/crm-service`

Classification:

- document-service and integration-hub runtime images are healthy;
- container-local pytest is unavailable in those images, so host-side container pytest gaps are `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` only while runtime health/smoke proof remains green;
- logistics-service health is green and owns preview compute;
- CRM remains compatibility/shadow, not canonical portal owner.

Required review checks:

- ensure no provider fake-success wording enters production mode;
- ensure unsupported providers return explicit degraded/unsupported states.

### S5 Admin Portal

Main contour groups:

- runtime center and diagnostics;
- cases/support canonical pages;
- finance/legal/CRM/commercial/logistics inspection;
- marketplace moderation;
- admin user write flows;
- retired fake KPI/dashboard/legacy health surfaces.

Verification already captured:

- admin build: PASS;
- admin vitest: PASS, `65 files / 166 tests`;
- admin smoke: PASS;
- manual browser flow: admin login, admin-user creation, moderation visibility PASS.

Review focus:

- confirm deleted legacy support/admin pages are truly replaced by mounted canonical pages;
- no raw payloads as UI;
- no blanket green provider/runtime cards.

### S6 Client Portal

Main contour groups:

- `portal/me`-derived workspace and client kind;
- no manual fake switch between individual/fleet;
- canonical cases/docs/finance/marketplace/logistics read states;
- frozen write/provider contours stay unavailable/frozen.

Verification already captured:

- client build: PASS;
- client vitest: PASS;
- client smoke: PASS;
- manual browser flow: client mode indicator derived from portal state PASS.

Review focus:

- client `org_type`/composition must come from backend `portal/me`;
- no local OTP/provider fake behavior;
- no hidden demo fallback on normal routes.

### S7 Partner Portal

Main contour groups:

- workspace shell from `portal/me + kind + capabilities`;
- partner onboarding route;
- marketplace product create and submit-to-moderation;
- support, profile/legal/team/locations;
- finance read shell and payout request path;
- `/contracts` and `/settlements*` remain frozen deep links only.

Verification already captured:

- partner build: PASS;
- partner vitest: PASS, `27 files / 73 tests`;
- partner smoke: PASS;
- manual browser flow: product create and submit moderation PASS.

Review focus:

- no fake finance/service/order summaries;
- no wrong-workspace entrypoints;
- frozen finance tails not present as normal navigation.

### S8 Shared Brand

Scope:

- `frontends/shared/brand/components/*`
- `frontends/shared/brand/tokens/*`
- `brand/v1/neft-client/tokens.client.css`

Review focus:

- shared states should distinguish grounded, first-use, filtered-empty, retry, access-limited, frozen/not-configured;
- avoid blind cleanup of client portal CSS unless route-owner migration requires it.

### S9 Browser Smoke

Scope:

- `frontends/e2e/tests/admin-smoke.spec.ts`
- `frontends/e2e/tests/client-smoke.spec.ts`
- `frontends/e2e/tests/partner-smoke.spec.ts`
- `frontends/e2e/tests/utils.ts`
- `frontends/e2e/tests/utils/ui_snapshot.ts`

Verification already captured:

- Playwright admin/client/partner smoke: PASS, `3 passed`.

Review focus:

- smoke should use explicit demo credentials/env;
- smoke should not encode fake provider success.

### S10 Readiness / Docs

Scope:

- scenario matrices;
- platform readiness map;
- portal truth maps;
- ADRs;
- evidence catalog/index;
- provider/external failure runbooks;
- pre-external exclusion taxonomy.

Review focus:

- statuses must use the final taxonomy consistently;
- green wording only for mounted runtime proof;
- frozen/provider-backed contours remain explicit exclusions.

### S11 Scripts / Smoke

Scope:

- seed scripts;
- portal smoke;
- marketplace/partner money/clearing/reconciliation/cards/support/observability smoke;
- ops helpers.

Verification already captured:

- `cmd /c scripts\smoke_all_portals.cmd`: PASS;
- marketplace/support/money/clearing/reconciliation/cards/observability smokes: PASS.

Review focus:

- scripts should leave generated outputs under ignored/temp locations;
- no committed scratch JSON/log output.

### S12 Ops Snapshot

Scope:

- `.ops` access/snapshot skeleton.

Review focus:

- decide whether `.ops` belongs in repo or should be local-only/ignored;
- do not mix this with product runtime changes.

### S13 Root Deletions / Gateway / AI Scorer

Root deletions requiring review:

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
- root smoke/helper/scratch files listed in `REPO_HYGIENE_20260421.md`

Other modified paths in this slice:

- `gateway/default.conf`
- `gateway/nginx.conf`
- `platform/ai-services/risk-scorer/**`

Review focus:

- split gateway route changes from root helper deletions;
- verify AI/risk remains deterministic-owner compatible and does not imply ML-ready business ownership;
- accept root deletions only if current docs/scripts no longer need them and replacement instructions exist.

## Staging Strategy

Recommended safe staging pattern:

```powershell
git status --porcelain
git diff --name-status -- <slice-paths>
git diff --check -- <slice-paths>
git add -- <slice-paths>
git status --porcelain
```

Avoid:

```powershell
git add .
git restore .
git checkout -- .
git reset --hard
```

Suggested split if preparing commits:

1. `pre-external-backend-core`
2. `pre-external-auth-and-satellite-services`
3. `pre-external-admin-portal`
4. `pre-external-client-portal`
5. `pre-external-partner-portal`
6. `pre-external-shared-brand-e2e`
7. `pre-external-smoke-scripts`
8. `pre-external-readiness-docs`
9. `pre-external-retired-surfaces`

## Acceptance Before External API Phase

Proceed only when:

- each slice has an owner-reviewed diff;
- risky deletions are accepted as retirements or replaced with current equivalents;
- generated artifacts remain absent from `git status`;
- targeted backend and frontend evidence remains green after any further edit;
- provider-backed/unmounted contours remain explicit exclusions until provider phase.

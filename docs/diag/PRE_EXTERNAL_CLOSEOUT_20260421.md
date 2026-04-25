# Pre-External Closeout Evidence - 2026-04-21

## Repo Hygiene Snapshot

`git status --porcelain` before cleanup:

| Status | Count | Classification |
| --- | ---: | --- |
| `M` | 983 | intended/product/docs/test changes plus existing large dirty worktree |
| `D` | 66 | requires release-owner review before any restore/removal decision |
| `??` | 226 | mostly new docs/tests/runtime contours plus generated artifacts |

Cleanup performed in this closeout was limited to exact generated files:

- `frontends/test-results/.last-run.json`
- `frontends/test-results`
- `frontends/login_admin_LOGIN_INPUTS_NOT_FOUND_1776656946636.png`
- `generate_invoice.json`
- `invoices.json`
- `.npm-cache`
- `Microsoft`
- `frontends/client-portal/.vitest-client.json`
- `scripts/_tmp`
- `frontends/ui-audit`

No git reset, checkout restore, or broad recursive cleanup was used.

`git status --porcelain` after cleanup and closeout reports:

| Status | Count | Classification |
| --- | ---: | --- |
| `M` | 983 | large intended/product/docs/test changes plus existing dirty worktree |
| `D` | 66 | requires release-owner review before any restore/removal decision |
| `??` | 220 | mostly new docs/tests/runtime contours; generated artifacts above were removed |

Detailed repo hygiene inventory and risky deletion list: `docs/diag/REPO_HYGIENE_20260421.md`.

Reviewable release patch slices: `docs/diag/RELEASE_PATCH_SLICES_20260421.md`.

## Runtime And Seed Evidence

| Check | Result | Notes |
| --- | --- | --- |
| `docker compose up -d --build core-api auth-host gateway admin-web client-web partner-web` | PASS | Key runtime services and portal images rebuilt. |
| `docker compose ps` | PASS | Gateway, core-api, auth-host, integration-hub, logistics-service, CRM, document-service, portals, and observability stack were up/healthy where health checks exist. |
| `cmd /c scripts\seed.cmd` | PASS | Canonical admin/client/partner demo identities reseeded. |
| `cmd /c scripts\seed_partner_money_e2e.cmd` | PASS | Partner finance/marketplace runtime data reseeded. |
| `/api/core/portal/me` client probe | PASS | `actor_type=client`, `context=client`, `org_type=INDIVIDUAL`, `access_state=NEEDS_ONBOARDING`. |
| `/api/core/portal/me` partner probe | PASS | `actor_type=partner`, `kind=MARKETPLACE_PARTNER`, marketplace/finance/support/profile workspaces and marketplace+finance capabilities present. |

## Automated Verification

| Command | Result | Classification |
| --- | --- | --- |
| `docker compose exec -T core-api pytest app/tests/test_portal_me_partner_alignment.py app/tests/test_admin_seed_partner_money.py app/tests/test_support_cases_bridge.py app/tests/test_case_storage_truth.py app/tests/test_client_logistics_api.py app/tests/test_admin_runtime_summary.py app/tests/test_marketplace_orders_e2e_v1.py app/tests/test_client_marketplace_v1.py -q` | PASS, `32 passed` | `VERIFIED_RUNTIME` targeted core gate. |
| `docker compose exec -T auth-host pytest app/tests/test_admin_users_audit.py app/tests/test_admin_users_schema.py app/tests/test_admin_users_topology.py app/tests/test_login_portal_claims.py -q` | PASS, `11 passed` | `VERIFIED_RUNTIME`; one stale UUID expectation was corrected in the test. |
| `docker compose exec -T document-service pytest ...` / `python -m pytest ...` | BLOCKED | Runtime image has no `pytest`; classify as `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` when compose health remains green. |
| `docker compose exec -T integration-hub pytest ...` / `python -m pytest ...` | BLOCKED | Runtime image has no `pytest`; classify as `HARNESS_EXCEPTION_NOT_RUNTIME_BLOCKER` when compose health remains green. |
| `npm.cmd run build` in `frontends/admin-ui` | PASS | Build green; only bundle-size/module-type warnings. |
| `npm.cmd run build` in `frontends/client-portal` | PASS | Build green; only module-type warning. |
| `npm.cmd run build` in `frontends/partner-portal` | PASS | Build green; only bundle-size/module-type warnings. |
| `npx.cmd vitest run` in `frontends/admin-ui` | PASS, `65 files / 166 tests` | UI unit/regression gate green. |
| `npx.cmd vitest run` in `frontends/client-portal` | PASS | UI unit/regression gate green; logs include expected test-only route/auth warnings. |
| `npx.cmd vitest run` in `frontends/partner-portal` | PASS, `27 files / 73 tests` | UI unit/regression gate green. |
| `cmd /c scripts\smoke_all_portals.cmd` | PASS | Portal smoke aggregate green. |
| `npx.cmd playwright test --config playwright.config.ts --project=chromium --reporter=list e2e/tests/admin-smoke.spec.ts e2e/tests/client-smoke.spec.ts e2e/tests/partner-smoke.spec.ts` | PASS, `3 passed` | Browser login smoke green after explicit demo credentials were supplied. |

## Runtime Smoke Evidence

| Command | Result |
| --- | --- |
| `cmd /c scripts\smoke_marketplace_order_loop.cmd` | PASS |
| `cmd /c scripts\smoke_partner_money_e2e.cmd` | PASS |
| `cmd /c scripts\smoke_clearing_batch.cmd` | PASS |
| `cmd /c scripts\smoke_reconciliation_request_sign.cmd` | PASS |
| `cmd /c scripts\smoke_cards_issue.cmd` | PASS |
| `cmd /c scripts\smoke_support_ticket.cmd` | PASS |
| `cmd /c scripts\smoke_observability_stack.cmd` | PASS |

## Manual Browser Flow Evidence

A temporary Playwright closeout probe was created, executed, and removed. It verified:

- admin login and admin-user creation through `/admin/admins/new`
- client login and read-only client mode indicator derived from portal state
- partner login, marketplace product creation, and submit-to-moderation through `/partner/products`
- admin marketplace moderation queue visibility for the newly submitted product

Result: PASS, `1 passed`.

The temporary spec was not retained in the repository to avoid turning a one-off closeout probe into a permanent broad E2E contract.

## Final Classification Notes

- `document-service` and `integration-hub` runtime images lacking `pytest` are harness exceptions, not runtime failures, because compose health is green and provider/internal owner health is covered separately.
- Frozen contours remain out of green acceptance: partner `/contracts`, partner `/settlements*`, client logistics provider-backed fuel-consumption writes, marketplace recommendation/consequence tails without mounted owner, and provider-backed OTP/email/SMS/live EDO/bank/ERP/fuel.
- Backend pytest may mutate live demo state; run `cmd /c scripts\seed.cmd` and `cmd /c scripts\seed_partner_money_e2e.cmd` after backend tests before browser/manual verification.

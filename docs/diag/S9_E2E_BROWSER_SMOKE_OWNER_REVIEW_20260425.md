# S9 E2E Browser Smoke Owner Review Closeout - 2026-04-25

## Scope

This review covers S9 from `docs/diag/RELEASE_PATCH_SLICES_20260425.md`:

- `frontends/e2e/**`

No staging, commits, branch split, patch bundle generation, public API changes, money semantic changes, auth semantic changes, or route-family removals were performed.

## S9 E2E Browser Smoke

Review-visible S9 scope after harness cleanup:

| Status | Count |
| --- | ---: |
| `M` | 22 |
| `D` | 0 |
| `??` | 3 |
| Total | 25 |

Primary owner areas:

- portal smoke specs for admin/client/partner login
- partner finance mounted-route browser sentinel
- UI snapshot helper utilities
- live-smoke helper scripts under `frontends/e2e/scripts`
- local Playwright package lock and runner configuration

## Deletion Review

S9 has no deleted files.

## Harness Fix

The first targeted Playwright run failed before browser execution because e2e files mixed two Playwright runner entrypoints:

- `@playwright/test` resolved through the parent `frontends/node_modules`
- `playwright/test` resolved through local `frontends/e2e/node_modules`

That produced the standard duplicate-runner failure: `Playwright Test did not expect test() to be called here`.

Fix:

- `frontends/e2e/playwright.e2e.config.ts` now imports `defineConfig` from `playwright/test`
- all e2e specs now import `test`/`expect` from `playwright/test`
- `partner-finance-mounted.spec.ts` uses the local runner and stays aligned

This is a harness blocker fix, not a product route change.

## Runtime Prerequisite

Partner finance browser truth requires the finance-capable seeded partner workspace.

Observed behavior before seeding:

- admin/client/partner login smokes passed
- `/partner/contracts` redirects away when `partner@neft.local` does not currently have the finance workspace in live runtime

Required prerequisite:

- `cmd /c scripts\seed_partner_money_e2e.cmd`

After this seed, `partner@neft.local` resolves the finance workspace and the mounted read-only `/contracts` and `/settlements*` browser sentinel is valid.

## Generated Artifact Policy

The targeted Playwright run produced `frontends/e2e/test-results/*`. This is generated runtime output and remains ignored by the repo hygiene policy. It is not S9 launch evidence and must not be staged.

## Checks

| Check | Result |
| --- | --- |
| `docker compose ps gateway core-api admin-web client-web partner-web auth-host` | PASS; all required services were up, gateway/core/auth healthy |
| initial targeted Playwright run | FAIL; duplicate Playwright runner imports, fixed in this slice |
| `cmd /c scripts\seed_partner_money_e2e.cmd` | PASS; finance-capable `partner@neft.local` seeded |
| targeted Playwright: `admin-smoke`, `client-smoke`, `partner-smoke`, `partner-finance-mounted` | PASS, `4` tests |
| generated `frontends/e2e/test-results/*` status | ignored generated output, not review evidence |

## Review Decision

S9 is reviewable as an e2e/browser-smoke owner slice. No risky deletions are present, the Playwright duplicate-runner harness blocker is fixed, generated browser output is ignored, and the changed smoke specs pass after the documented seed prerequisite.

Final packaging still must use explicit S9 pathspecs. Do not stage `frontends/e2e/test-results`, Playwright reports, or unrelated runtime screenshots with this slice.

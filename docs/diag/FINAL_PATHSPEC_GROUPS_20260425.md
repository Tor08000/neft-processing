# Final Pathspec Groups - 2026-04-25

## Purpose

This file collects final review/staging pathspec groups for the current NEFT full-repo hardening workstream.

It is a packaging map only. No staging, commits, branch split, or patch bundle generation was performed while creating it.

Rules:

- never use `git add .`;
- stage one owner slice at a time;
- keep `.env`, generated scratch, Playwright reports, and ops snapshots out of staged release slices;
- include deletions only in the owner slice that documents replacement/freeze evidence.

## Always Exclude

Do not stage:

- `.env`
- `accept`
- `scripts/_tmp/`
- `frontends/**/test-results/`
- `frontends/**/playwright-report/`
- `.ops/snapshots/`
- `.ops/access.ps1`
- `.ops/kubeconfig.yaml`
- root smoke JSON/TXT outputs ignored by `.gitignore`

## Owner Slice Pathspec Groups

S1 root/gateway/infra:

```powershell
git add -- .dockerignore .gitignore .env.example docker-compose.yml gateway
```

S2 processing-core:

```powershell
git add -- platform/processing-core
```

S3 auth-host:

```powershell
git add -- platform/auth-host
```

S4 satellite/backend services:

```powershell
git add -- platform/document-service platform/integration-hub platform/logistics-service platform/crm-service platform/ai-services platform/billing-clearing
```

S5 admin-ui:

```powershell
git add -- frontends/admin-ui
```

S6 client-portal:

```powershell
git add -- frontends/client-portal
```

S7 partner-portal:

```powershell
git add -- frontends/partner-portal
```

S8 shared brand:

```powershell
git add -- frontends/shared brand
```

S9 e2e/browser smoke:

```powershell
git add -- frontends/e2e frontends/docs/UI_SNAPSHOT_RUNBOOK.md ':!frontends/e2e/test-results' ':!frontends/e2e/playwright-report'
```

S11 scripts/smokes:

```powershell
git add -- scripts ':!scripts/_tmp'
```

S10 docs/evidence:

```powershell
git add -- docs
```

S12 ops snapshot templates:

```powershell
git add -- .ops/README.md .ops/access.example.ps1
```

S13 root misc/generated/risky deletions:

```powershell
git add -- shared/python/neft_shared/logging_setup.py shared/python/neft_shared/settings.py sitecustomize.py tests_host/test_fuel_provider_replay_batch.py admin_login.json admin_tests.cmd ai_tests.cmd auth_tests.cmd curl diag_v021.txt docs_client_logistics_not_found_report.md find_auth_endpoints.py index.html inspect_neft_repo.py req.json run_tests.cmd selftest.cmd structure.txt tree_to_file.cmd
```

## Review Notes

- S1 intentionally excludes `.env`; `.env` is local verification state only.
- S12 intentionally excludes `.ops/snapshots/*`; generated ops snapshots are not launch evidence.
- S13 no longer contains root project-entrypoint deletion blockers. `.pre-commit-config.yaml`, `AGENTS.md`, `CHANGELOG.md`, `Makefile`, `README.md`, `conftest.py`, `pytest.ini`, `docker-compose.dev.yml`, `docker-compose.smoke.yml`, and `docker-compose.test.yml` were restored from `HEAD`.
- A reviewer may split S10 docs/evidence further, but any split must keep `docs/diag/LAUNCH_EVIDENCE_LOCK_20260425.md`, `docs/diag/RELEASE_PATCH_SLICES_20260425.md`, and this file together.

## Verification Before Staging

Run before staging any slice:

```powershell
git status --porcelain=v1
git diff --check -- docs .gitignore shared/python/neft_shared/logging_setup.py shared/python/neft_shared/settings.py sitecustomize.py
```

For product slices, use the checks recorded in `docs/diag/RELEASE_PATCH_SLICES_20260425.md` and the evidence lock.

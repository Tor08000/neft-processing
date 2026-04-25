# S1/S2 Owner Review Closeout - 2026-04-25

## Scope

This review covers only the first two slices from `docs/diag/RELEASE_PATCH_SLICES_20260425.md`:

- S1 root/gateway/infra
- S2 `processing-core`

No staging, commits, branch split, patch bundles, destructive cleanup, public API removal, money formula changes, or auth semantic changes were performed.

## S1 Root/Gateway/Infra

Review-visible S1 scope:

- `.dockerignore`
- `.env`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `gateway/default.conf`
- `gateway/nginx.conf`

Finding:

- `.dockerignore` did not exclude `.env` from Docker build context after the hygiene rewrite.
- `services/admin-web/.env` and `services/auth-host/.env` were untracked local wrapper env files and visible to review status.
- root smoke JSON/TXT outputs, `scripts/_tmp`, Playwright `test-results`, and old `docs/diag/*.txt` diagnostics were mixed with reviewable product/evidence files.

Fix:

- `.dockerignore` now excludes local `.env`, `.admin_token`, cache folders, `services/*/.env`, and local generated markers from build context.
- `.gitignore` now excludes `.env`, service-wrapper `.env`, `scripts/_tmp`, Playwright output, root smoke scratch JSON/TXT files, and old generated diag text/openapi scratch.
- `docs/diag` JSON evidence and screenshots remain reviewable; no blanket `*.json` or `*.png` ignore was added.

Guard:

- `.env` is still a tracked modified local verification file. It was not staged or accepted by this review and must not be included in release packaging unless explicitly approved.

Checks:

| Check | Result |
| --- | --- |
| `docker compose config --quiet` | PASS |
| `docker compose exec -T gateway nginx -t` | PASS |
| `git check-ignore -v services/admin-web/.env services/auth-host/.env scripts/_tmp/... frontends/e2e/test-results/... docs/diag/neft_state_*.txt` | PASS |

## S2 Processing-Core

Review-visible S2 scope:

| Status | Count |
| --- | ---: |
| `M` | 514 |
| `D` | 9 |
| `??` | 113 |
| Total | 636 |

Primary owner areas in this slice:

- admin/operator routes and capability gates
- client portal/logistics/marketplace/documents/support surfaces
- partner finance/context/support bridges
- documents/docflow/EDO orchestration
- marketplace order/SLA/settlement helpers
- logistics persisted evidence and preview split
- AI/risk/explain/audit linkage
- BI optional disabled truth
- migrations and isolated test harnesses

Deletion candidates under S2:

- `platform/processing-core/app/api/v1/endpoints/admin_clearing.py`
- `platform/processing-core/app/routers/admin_me_legacy.py`
- `platform/processing-core/app/routers/admin_runtime_legacy.py`
- `platform/processing-core/services/audit_log.py`
- `platform/processing-core/services/billing.py`
- `platform/processing-core/services/clearing.py`
- `platform/processing-core/services/pricing.py`
- `platform/processing-core/services/risk_adapter.py`
- `platform/processing-core/services/rules_engine.py`

Deletion review result:

- No live imports to the deleted `platform/processing-core/services/*` modules were found; current imports resolve through `app.services.*` or `app/services.py`.
- `admin_clearing.py` is replaced by `app.routers.admin.clearing`.
- `admin_me_legacy.py` and `admin_runtime_legacy.py` are replaced by canonical admin owner routes and the narrowed `admin_legacy_aliases` compatibility map.
- These deletions are still not accepted globally by this document. They are eligible for S2 owner staging only with this evidence and the passing sentinels below.

Host harness note:

- Host-side `python -m pytest ...` failed at collection because host Python lacks `fastapi`.
- This is classified as a local harness limitation; runtime validation was executed inside the healthy `core-api` container.

Checks:

| Check | Result |
| --- | --- |
| `docker compose exec -T core-api pytest app/tests/test_admin_runtime_summary.py app/tests/test_admin_clearing_run.py app/tests/test_admin_clearing_storage_truth.py app/tests/test_marketplace_orders_e2e_v1.py app/tests/test_marketplace_order_sla_access.py app/tests/test_client_marketplace_v1.py app/tests/test_client_logistics_api.py app/tests/test_support_cases_bridge.py app/tests/test_case_storage_truth.py app/tests/test_bi_optional_truth.py app/tests/test_decision_memory_audit.py app/tests/test_risk_adapter_truth.py -q` | PASS, `36 passed` |
| `docker compose exec -T core-api pytest app/tests/test_hidden_gateway_aliases_topology.py app/tests/test_admin_me_capabilities.py app/tests/test_admin_portal_access.py app/tests/test_admin_marketplace_capability.py -q` | PASS, `28 passed` |
| `docker compose exec -T core-api python -m compileall -q app` | PASS |

## Review Decision

S1 and S2 are now reviewable owner slices. Final packaging must still use explicit pathspecs and must not stage `.env`, generated scratch, or unrelated root deletion tails.

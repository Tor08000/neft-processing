# BI / Analytics Truth Map

Date: 2026-04-25

## Launch Decision

ClickHouse-backed BI dashboards are now `VERIFIED_RUNTIME` for the local launch gate.

This wave changed the local gate from "optional disabled is acceptable" to "ClickHouse must be enabled and proven":

- `scripts/compose_launch_gate.cmd` exports `BI_CLICKHOUSE_ENABLED=1` without writing secrets to `.env`.
- The compose gate starts `clickhouse` and `clickhouse-init` together with the core services.
- Admin BI sync must return `200` and persist a completed sync run before dashboard smokes run.
- Ops, partner, client-spend, and CFO dashboard smokes must return `200` payloads.
- Disabled-mode sentinels remain in tests, but `bi_disabled` no longer satisfies the local launch gate.

## Owner Map

| Contour | Owner | Current gate | Runtime behavior |
|---|---|---|---|
| Raw BI event reads and BI exports | `processing-core` `/api/v1/bi/*` | `VERIFIED_RUNTIME` when launch gate enables ClickHouse | reads/export flow against BI marts; disabled mode fails closed in tests |
| Client dashboard analytics | `processing-core` `/api/core/bi/*` | `VERIFIED_RUNTIME` | Postgres BI mart projections backed by ClickHouse sync |
| Admin BI sync | `processing-core` `/api/core/v1/admin/bi/sync/*` | `VERIFIED_RUNTIME` | audited `INIT` and `INCREMENTAL` sync runs return `200` |
| ClickHouse transport | `processing-core` `app.services.bi.clickhouse` | launch-gated runtime storage | retrying JSONEachRow writes when enabled; explicit disabled result only outside launch gate |
| Smoke evidence | `scripts/smoke_bi_*_dashboard.cmd` | mandatory launch proof | requires `200` dashboard payload; no `SKIP_OK` path in the launch gate |

## Compatibility / Route Truth

Canonical dashboard family:

- `/api/core/bi/metrics/daily`
- `/api/core/bi/declines`
- `/api/core/bi/orders/summary`
- `/api/core/bi/documents/summary`
- `/api/core/bi/exports/summary`
- `/api/core/bi/spend/summary`
- `/api/core/bi/cfo/*`
- `/api/core/bi/ops/*`
- `/api/core/bi/partner/*`
- `/api/core/bi/client/*`

Raw/export family:

- `/api/v1/bi/*`

Admin sync family:

- `/api/core/v1/admin/bi/sync/init`
- `/api/core/v1/admin/bi/sync/run`

No public route is removed in this wave.

## Sentinel Coverage

| Sentinel | What it freezes |
|---|---|
| `test_bi_optional_truth.py::test_bi_disabled_blocks_dashboard_and_raw_export_without_fake_empty_success` | BI disabled cannot return fake `200` empty dashboard/export success outside the launch gate |
| `test_bi_optional_truth.py::test_bi_disabled_blocks_admin_sync_as_explicit_optional_not_configured` | Admin sync remains explicit `409 bi_disabled` when ClickHouse is intentionally off |
| `test_bi_optional_truth.py::test_clickhouse_sync_disabled_returns_explicit_task_result` | Direct ClickHouse sync task cannot silently no-op as success |
| `test_bi_optional_truth.py::test_bi_sync_run_response_accepts_orm_instance` | Admin sync API serializes persisted run rows instead of failing on ORM response shape |
| `test_bi_optional_truth.py::test_bi_dashboard_tenant_resolver_accepts_uuid_admin_claim` | Admin dashboard probes tolerate seeded UUID tenant claims |
| `test_bi_client_dashboards_wave*.py` | Dashboard/read contracts still work when BI is enabled in tests |
| `test_bi_raw_v1.py` | Raw BI reads/export access, tenant checks, and export states remain covered when enabled |

## Live Evidence

Current evidence file:

- `docs/diag/bi-analytics-truth-live-smoke-20260425.json`

Captured launch-gate commands:

- `cmd /c scripts\compose_launch_gate.cmd`
- `cmd /c scripts\smoke_bi_ops_dashboard.cmd`
- `cmd /c scripts\smoke_bi_partner_dashboard.cmd`
- `cmd /c scripts\smoke_bi_client_spend_dashboard.cmd`
- `cmd /c scripts\smoke_bi_cfo_dashboard.cmd`

The evidence records:

- `BI_CLICKHOUSE_ENABLED=true`
- completed `INIT` and `INCREMENTAL` sync runs
- `200` Ops SLA dashboard payload
- `200` partner performance dashboard payload
- `200` client spend dashboard payload
- `200` CFO overview dashboard payload

Historical disabled-mode proof remains useful as regression coverage only; it is not the launch classification.

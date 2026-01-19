# Sprint B — Ops Runtime Center (Acceptance)

## Stack bring-up

1. Build and run the stack:
   ```bash
   docker compose up -d --build
   ```
2. Apply migrations (Windows):
   ```cmd
   scripts\migrate.cmd
   ```
3. Wait for `/api/core/health` to return `"status":"ok"`.

## Admin token

On Windows, use the helper script:
```cmd
scripts\get_admin_token.cmd
```

The script prints the JWT. Use it as `Authorization: Bearer <token>` for admin requests.

## Ops overview

Open the Ops dashboard:
```
http://localhost/admin/ops
```

The page should load within 60 seconds and show:
* Signals status (GREEN/YELLOW/RED) with reasons.
* Queues, MoR invariants, Billing, Reconciliation.
* Exports + Support health.

## Smoke script (Windows CMD)

Run:
```cmd
scripts\smoke_admin_ops.cmd
```

The log is stored in:
```
logs\smoke_admin_ops_<date>.log
```

## Signals criteria

Status is computed server-side:
* **RED** when:
  * `immutable_violations_24h > 0`
  * `clawback_required_24h > 0`
  * payout queue backlog/blocked spike thresholds exceeded
* **YELLOW** when:
  * `overdue_orgs` above threshold
  * `exports.failed_1h` above threshold
  * `reconciliation.parse_failed_24h > 0`
* **GREEN** otherwise.

## Acceptance checklist

* `/admin/ops` shows a single status and reasons.
* Backend computes status; frontend only renders.
* Ops dashboard includes queues, MoR invariants, billing overdue, reconciliation health, exports/support.
* Drilldown endpoints return last N failures.
* `scripts\smoke_admin_ops.cmd` passes and is included in `scripts\verify_all.cmd`.

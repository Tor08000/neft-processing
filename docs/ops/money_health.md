# Money Health diagnostics

## Endpoint
`GET /api/core/v1/admin/money/health`

## What it checks
- Orphan ledger transactions (ledger tx without money flow linkage)
- Missing ledger postings (settled flows without ledger tx)
- Ledger invariant violations (unbalanced or mixed currency postings)
- Stuck flows in `AUTHORIZED` or `PENDING_SETTLEMENT`
- Cross-period anomalies (`meta.cross_period=true`)

## Parameters
- `stale_hours` (default: 24): how old an `AUTHORIZED`/`PENDING_SETTLEMENT` flow must be to count as stuck.

## Response fields
- `orphan_ledger_transactions`
- `missing_ledger_postings`
- `invariant_violations`
- `stuck_authorized`
- `stuck_pending_settlement`
- `cross_period_anomalies`
- `top_offenders`

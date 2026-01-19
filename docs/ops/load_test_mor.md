# MoR Load Test (Settlement + Ledger + Payout) — Sprint G1

This document describes the **money-contour load test** for MoR settlement.
It validates settlement finalization, ledger posting, and payout batching
at production-scale load.

## Scope

**What we load**

- 10,000 marketplace orders
- 1,000 partners
- 100 payout batches
- SLA penalties on a subset of orders
- mixed currencies (if enabled via flag)
- settlement finalization (snapshot + ledger + revenue)
- payout batching

**What we verify**

- no drift between settlement snapshot, partner ledger, and platform revenue
- no payout before `finalized_at`
- no recalculation after finalize (`settlement_immutable_violation_total == 0`)
- no double payout
- no negative balances without reason

## How to run

> The script uses an in-memory SQLite DB and **no mocks**. It runs fully offline.

```cmd
python scripts\load_mor_settlement.py --mixed-currencies
```

Optional (override defaults):

```cmd
python scripts\load_mor_settlement.py --orders 10000 --partners 1000 --payout-batches 100 --runs 3 --mixed-currencies
python scripts\load_mor_settlement.py --penalty-rate 0.05 --penalty-amount 10
python scripts\load_mor_settlement.py --output reports\mor_load.json --csv-output reports\mor_load.csv
```

## Output

The script prints a summary and writes JSON + CSV:

- `reports/load_mor_settlement.json`
- `reports/load_mor_settlement.csv`

```json
{
  "generated_at": "2025-01-01T12:00:00+00:00",
  "runs": [
    {
      "run_id": 1,
      "orders": 10000,
      "partners": 1000,
      "payout_batches_target": 100,
      "payout_batches_built": 100,
      "duration_seconds": 42.8,
      "payout_duration_seconds": 8.3,
      "settlement_snapshot_total": "850000",
      "ledger_total": "850000",
      "revenue_total": "150000",
      "payout_total": "850000",
      "payout_blocked_total": 0,
      "max_payout_batch_operations": 120,
      "max_payout_batch_total_amount": "10200",
      "error_rate": 0,
      "settlement_immutable_violation_total": 0,
      "payout_without_finalize_total": 0
    }
  ]
}
```

## Interpreting results

A run is **PASS** when:

- `error_rate == 0`
- `settlement_snapshot_total == ledger_total`
- `revenue_total` matches settlement fee totals
- `payout_total` equals settlement net total for payouted partners
- `payout_without_finalize_total == 0`
- `settlement_immutable_violation_total == 0`

## Report table (fill after execution)

| Run | Orders | Partners | Duration (s) | Payout (s) | Error rate | Max batch ops | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 10k | 1k |  |  |  |  |  |
| 2 | 10k | 1k |  |  |  |  |  |
| 3 | 10k | 1k |  |  |  |  |  |

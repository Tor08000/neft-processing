# MoR Load Test (Settlement + Ledger + Payout) — Sprint G1

This document describes the **money-contour load test** for MoR settlement.
It validates settlement finalization, ledger posting, and payout batching
at 1k/5k/10k order volumes.

## Scope

**What we load**

- 1k / 5k / 10k marketplace orders
- settlement finalization (snapshot + ledger + revenue)
- payout batching

**What we verify**

- no drift between settlement snapshot, partner ledger, and platform revenue
- no double payout
- no negative balances without reason

## How to run

> The script uses an in-memory SQLite DB and **no mocks**. It runs fully offline.

```cmd
python scripts\load_mor_settlement.py
```

Optional (run a single size and custom output file):

```cmd
python scripts\load_mor_settlement.py --orders 5000 --output reports\mor_load_5000.json
```

## Output

The script prints a summary and writes JSON to `reports/load_mor_settlement.json`:

```json
{
  "generated_at": "2025-01-01T12:00:00+00:00",
  "runs": [
    {
      "orders": 1000,
      "duration_seconds": 4.2,
      "payout_duration_seconds": 0.3,
      "settlement_snapshot_total": "85000",
      "ledger_total": "85000",
      "revenue_total": "15000",
      "payout_amount": "85000",
      "payout_blocked": false,
      "errors": []
    }
  ]
}
```

## Interpreting results

A run is **PASS** when:

- `errors` is empty
- `settlement_snapshot_total == ledger_total`
- `revenue_total` matches settlement fee totals
- `payout_amount` equals settlement net total

## Report table (fill after execution)

| Orders | Duration (s) | Payout (s) | Errors | Notes |
| --- | --- | --- | --- | --- |
| 1k |  |  |  |  |
| 5k |  |  |  |  |
| 10k |  |  |  |  |

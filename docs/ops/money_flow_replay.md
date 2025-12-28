# Money Flow Replay (v3)

## Endpoint
`POST /admin/money/replay`

Payload:

```
{
  "client_id": "...",
  "billing_period_id": "...",
  "mode": "DRY_RUN" | "COMPARE" | "REBUILD_LINKS",
  "scope": "SUBSCRIPTIONS" | "FUEL" | "ALL"
}
```

## Modes

### DRY_RUN
Recomputes charges/usage without persisting changes. Returns a deterministic `recompute_hash`.

### COMPARE
Compares recompute outputs to stored data. Returns diff summary:

- mismatched totals
- missing links
- broken snapshots
- recommended action

### REBUILD_LINKS
Rebuilds `money_flow_links` idempotently. Returns rebuilt link count.

## Notes
- No automatic fixes are applied in v3.
- Use the diff output for manual follow-up.

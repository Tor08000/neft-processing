# Money Flow v3

## Overview
Money Flow v3 hardens financial traceability by:

- Building a full money chain graph (usage → charges → invoice → payment → settlement → ledger).
- Recording deterministic invariant snapshots (BEFORE/AFTER).
- Providing CFO-level explainability for invoice totals and balances.
- Supporting safe replay/recompute diagnostics.
- Capturing negative scenarios with explicit tests and auditability.

## Core Concepts

### Money Flow Links
`money_flow_links` records directional relationships between money objects.

Typical edges:

- `SUBSCRIPTION → SUBSCRIPTION_CHARGE` (GENERATES)
- `SUBSCRIPTION_CHARGE → INVOICE` (GENERATES)
- `FUEL_TX → INVOICE` (FEEDS)
- `PAYMENT → INVOICE` (SETTLES)
- `INVOICE → LEDGER_TX` (POSTS)
- `PAYMENT → LEDGER_TX` (POSTS)

### Invariant Snapshots
For each critical money event:

- Record a `BEFORE` snapshot
- Apply the action
- Record an `AFTER` snapshot

Snapshots are canonical JSON with SHA-256 hash, stored in `money_invariant_snapshots`.

### CFO Explain
`/admin/money/cfo-explain` returns:

- invoice totals + breakdown
- charges / usage / ledger / payments links
- invariant snapshot status
- anomalies detected

### Replay & Compare
`/admin/money/replay` runs in one of these modes:

- `DRY_RUN` (deterministic recompute hash)
- `COMPARE` (snapshot diffs)
- `REBUILD_LINKS` (idempotent graph rebuild)

## Health Checks (v3)
`/admin/money/health` also reports:

- missing money flow links
- missing snapshots (BEFORE/AFTER)
- disconnected graphs (invoice without charges)
- CFO explain readiness flags

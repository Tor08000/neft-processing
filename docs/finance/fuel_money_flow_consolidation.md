# Fuel ↔ CRM ↔ Money Flow Consolidation (v1)

## Link map

**Fuel settlement/reversal**

- `FUEL_TX` → `LEDGER_TX` (`POSTS`)
- `FUEL_TX` → `BILLING_PERIOD` (`RELATES`)

**Invoice aggregation**

- `FUEL_TX` → `INVOICE` (`FEEDS`) when fuel transactions are included in invoice aggregation
- `INVOICE` → `DOCUMENT` (`GENERATES`) already exists; no duplication

## Replay scope: `FUEL`

Supported modes:

- `DRY_RUN` — recomputes fuel totals for the period:
  - `tx_count`
  - `volume_ml`
  - `amount_minor`
- `COMPARE` — compares recomputed totals with:
  - settled fuel transactions
  - fuel ledger postings (where present)
  - fuel invoice aggregation (if invoice exists)
  - returns missing links count, missing ledger postings, and mismatched totals
- `REBUILD_LINKS` — rebuilds:
  - `FUEL_TX` → `BILLING_PERIOD`
  - `FUEL_TX` → `LEDGER_TX`
  - `FUEL_TX` → `INVOICE` (if invoice is available)

## Metric gating (subscriptions)

Feature flag: `SUBSCRIPTION_METER_FUEL_ENABLED`.

- `false` — subscription usage ignores fuel metrics
- `true` — usage collector includes:
  - `FUEL_TX_COUNT`
  - `FUEL_VOLUME` (ml)

Tariffs can declare fuel metrics in `included`, `overage`, `caps`, or `metric_rules`.
Fuel totals are shown in CFO explain only when the flag is enabled and the tariff declares fuel metrics.

## Definition of Done

✅ Fuel settle/reverse creates money_flow_links (ledger + period)

✅ Replay supports `scope=FUEL` (`dry_run`/`compare`/`rebuild_links`)

✅ Fuel usage can be gated in subscription metrics via feature flag

✅ Health check reports missing fuel links

✅ Tests are green

# Realized margin mapping (auto-discovered)

## Discovery scope
- Schema scanned: `processing_core` via `pg_catalog.pg_tables` / SQLAlchemy inspector using patterns: `%settle%`, `%clearing%`, `%payout%`, `%ledger%`, `%recon%`, `%batch%`, `%item%`.
- SQLAlchemy model scan path: `platform/processing-core/app/models` with class-name keywords: `Settlement`, `Clearing`, `Payout`, `Ledger`, `Reconciliation`, `Batch`, `Item`.

## Chosen mapping
- Settlement (cost) line table: `clearing_batch_operation`.
- Revenue source table: `operations`.
- Join key: `clearing_batch_operation.operation_id = operations.operation_id`.
- Station key: `operations.fuel_station_id`.
- Day semantics: **UTC day**, derived from `operations.created_at`.

## Metric formulas
- `revenue_sum = SUM(COALESCE(NULLIF(operations.captured_amount, 0), operations.amount) / 100.0)` for captured/settled-like rows.
- `cost_sum = SUM(clearing_batch_operation.amount / 100.0)`.
- `gross_margin = revenue_sum - cost_sum`.
- `margin_pct = gross_margin / NULLIF(revenue_sum, 0)`.
- `tx_count = COUNT(operations.id)`.

## Status filter
- Included operation statuses: `CAPTURED`, `COMPLETED`.
- Declined operations are excluded.

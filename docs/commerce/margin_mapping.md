# Realized margin mapping (auto-discovered)

## Discovery scope
- Schema scanned: `processing_core` via `pg_catalog.pg_tables` / SQLAlchemy inspector using patterns: `%settle%`, `%clearing%`, `%payout%`, `%ledger%`, `%batch%`, `%item%`, `%line%`, `%entry%`.
- SQLAlchemy model scan path: `platform/processing-core/app/models` with class-name keywords: `settle`, `clearing`, `payout`, `ledger`, `batch`, `item`, `line`, `entry`.

## Chosen mapping
- **Cost source**: `clearing_batch_operation` (`amount`, `operation_id`), granularity = `LINE_ITEMS`.
- **Revenue source**: `operations` (`captured_amount` fallback to `amount`) filtered to `CAPTURED|COMPLETED`.
- **Join key**: `clearing_batch_operation.operation_id = operations.operation_id`.
- **Station key**: `operations.fuel_station_id`.
- **Day bucket**: UTC day from `operations.created_at`.

## Formulas
- `revenue_sum = SUM(COALESCE(NULLIF(operations.captured_amount, 0), operations.amount) / 100.0)`.
- `cost_sum = SUM(COALESCE(clearing_batch_operation.amount, 0) / 100.0)`.
- `gross_margin = revenue_sum - cost_sum`.
- `margin_pct = gross_margin / NULLIF(revenue_sum, 0)`.
- `tx_count = COUNT(operations.id)`.

## Assumptions and failure mode
- Monetary fields are stored in minor units (kopecks), therefore `/100.0` normalization is required.
- Settlement is considered cost-of-goods at operation-line level.
- If auto-discovery cannot find required mapping columns (`station`, `day`, `revenue`, settlement `amount` + `operation link`) the builder raises an explicit `MarginMappingError` with JSON mapping report and does **not** proceed.

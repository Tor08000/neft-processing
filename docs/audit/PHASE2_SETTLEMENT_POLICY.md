# Audit Phase 2 — Settlement Policy

## Canonical states

Target policy lifecycle for settlement period:

`open -> closing -> closed`

Current implementation has `OPEN/CALCULATED/APPROVED/PAID`; operationally this maps to:

- `OPEN` ~ open
- `CALCULATED/APPROVED` ~ closing
- `PAID` ~ closed/final

## Rules

### Allowed before close

- Normal refunds/reversals in same period (`SettlementPolicy.SAME_PERIOD`).
- Standard postings (`REFUND`, `REVERSAL`) impacting period balances.

### Forbidden after close

- Direct mutation of historical ledger rows.
- Editing/deleting posted entries.
- Re-opening old postings by update.

### Allowed after close

- Adjustment-only flow:
  - `SettlementPolicy.ADJUSTMENT_REQUIRED`
  - Posting type `ADJUSTMENT`
  - Adjustment record with reason and effective date in next period.

## Scenarios

1. **Refund inside open period**
   - Input: `settlement_closed=False`
   - Result: `REFUND` posting.

2. **Refund after close**
   - Input: `settlement_closed=True`
   - Result: `ADJUSTMENT` posting + `financial_adjustments` row.

3. **Reversal after close**
   - Input: `settlement_closed=True`
   - Result: adjustment layer only, without modifying old ledger entries.

4. **Duplicate reversal**
   - Result: domain error (`REVERSAL_ALREADY_EXISTS`), no second posting.

## Enforcement points

- Domain services: refund/reversal/dispute scenario services.
- Posting engine: append-only posting writes.
- Ledger model: update/delete guard for posted entries.

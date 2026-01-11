# Financial invariants (v1)

Financial invariants are math checks that must stay true after money moves.
If any invariant fails, the system raises a domain error and emits
`FINANCIAL_INVARIANT_VIOLATION` audit event with details.

## Invariants matrix

| Invariant | Applied after | Protects |
| --- | --- | --- |
| `invoice.total_with_tax = total_amount + tax_amount` | Invoice issue | Prevents inconsistent invoice totals. |
| `invoice.amount_due = total_with_tax - amount_paid - credited_amount + amount_refunded` | Invoice issue, payment, credit note, refund | Ensures due balance stays consistent with settlements. |
| `invoice.amount_due >= 0` | Invoice issue, payment, credit note, refund | Prevents negative due balances. |
| `invoice.amount_paid >= 0` | Invoice issue, payment | Prevents negative paid balances. |
| `invoice.amount_refunded >= 0` | Invoice issue, refund | Prevents negative refunds. |
| `invoice.credited_amount >= 0` | Credit note | Prevents negative credit note totals. |
| `paid + credited - refunded + due == total_with_tax` | Invoice issue, payment, credit note, refund | Ensures full balance equation stays closed. |
| `payment.amount <= invoice.amount_due` | Payment apply | Prevents overpayment. |
| `payment.invoice_status != CANCELLED` | Payment apply | Prevents applying payments to voided invoices. |
| `refund.amount <= amount_paid - amount_refunded` | Refund | Prevents over-refunding. |
| `alloc_net == paid_total - refund_total - credited_total` | Settlement allocation | Ensures settlement allocations match net coverage. |
| `abs(alloc_net) <= invoice.total_with_tax` | Settlement allocation | Prevents allocation overflow across periods. |
| `settlement_period.status != LOCKED` (unless override) | Settlement allocation | Prevents changes in closed settlement periods. |
| `ΣDEBIT == ΣCREDIT` per currency | Ledger posting | Ensures double-entry postings stay balanced. |
| `ledger_entry.currency == account.currency` | Ledger posting | Prevents currency mismatches in accounts. |

## Audit payload

Every violation emits `FINANCIAL_INVARIANT_VIOLATION` with payload:

```json
{
  "entity": "invoice|payment|ledger_transaction",
  "invariants": [
    {
      "name": "invoice.amount_due",
      "expected": 1000,
      "actual": 1200
    }
  ],
  "ledger_transaction_id": "..."
}
```

## Settlement allocation coverage

`alloc_net` is computed as payment allocations minus credit note allocations minus refund allocations.
`net coverage` is computed as `paid_total - refund_total - credited_total`, where paid totals are derived from invoice payments and refunds/credits are derived from invoice totals. The settlement allocation invariant asserts these stay aligned after each payment, credit note, or refund, and reconciliation is invoked after those operations to backfill missing allocations when needed.

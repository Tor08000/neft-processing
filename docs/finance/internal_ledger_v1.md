# Internal Ledger v1

Internal ledger provides a deterministic, idempotent, auditable double-entry layer without replacing existing
invoices/payments. It is used as the audit source of truth.

## Accounts

Internal ledger accounts live in `internal_ledger_accounts` with the following types:

- `CLIENT_AR`
- `CLIENT_CASH`
- `PLATFORM_REVENUE`
- `PLATFORM_FEES`
- `TAX_VAT`
- `PROVIDER_PAYABLE`
- `SUSPENSE`

Each account is unique per `(tenant_id, client_id, account_type, currency)`.

## Transactions

Transaction headers are stored in `internal_ledger_transactions` with deterministic idempotency keys:

- Invoice issued: `invoice:{invoice_id}:issued:v1`
- Payment applied: `payment:{payment_id}:applied:v1`
- Credit note applied: `credit_note:{credit_note_id}:applied:v1`
- Refund applied: `refund:{refund_id}:applied:v1`

## Entries

Entries are stored in `internal_ledger_entries` and are hashed deterministically:

```
entry_hash = sha256(canonical_json({
  tenant_id,
  ledger_transaction_id,
  account_id,
  direction,
  amount,
  currency
}))
```

## Posting rules

### Invoice issued

When an invoice is issued:

- **DEBIT** `CLIENT_AR` for `total_with_tax`
- **CREDIT** `PLATFORM_REVENUE` for `total_amount`
- **CREDIT** `TAX_VAT` for `tax_amount` (if > 0)

### Payment applied

When a payment is applied to an invoice:

- **DEBIT** `CLIENT_CASH` for payment amount
- **CREDIT** `CLIENT_AR` for payment amount

### Credit note applied

When a credit note is applied:

- **DEBIT** `PLATFORM_REVENUE` for credit note amount
- **CREDIT** `CLIENT_AR` for credit note amount

### Refund applied

When a refund is applied:

- **DEBIT** `CLIENT_AR` for refund amount
- **CREDIT** `CLIENT_CASH` for refund amount

## Health checks

Admin endpoint:

```
GET /admin/ledger/health
```

Response fields:

- `broken_transactions_count`: ledger transactions where debits != credits.
- `missing_postings_count`: invoices/payments missing ledger postings.

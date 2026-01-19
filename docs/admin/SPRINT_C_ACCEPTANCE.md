# Sprint C Acceptance — Finance & MoR Control

## Routes

### Finance overview
- `GET /api/core/v1/admin/finance/overview?window=24h|7d`

### Invoices
- `GET /api/core/v1/admin/finance/invoices`
- `GET /api/core/v1/admin/finance/invoices/{invoice_id}`
- `POST /api/core/v1/admin/finance/invoices/{invoice_id}/mark-paid`
- `POST /api/core/v1/admin/finance/invoices/{invoice_id}/void`
- `POST /api/core/v1/admin/finance/invoices/{invoice_id}/mark-overdue`

### Payment intakes
- `GET /api/core/v1/admin/finance/payment-intakes`
- `GET /api/core/v1/admin/finance/payment-intakes/{id}`
- `POST /api/core/v1/admin/finance/payment-intakes/{id}/approve`
- `POST /api/core/v1/admin/finance/payment-intakes/{id}/reject`

### Reconciliation imports
- `GET /api/core/v1/admin/reconciliation/imports`
- `GET /api/core/v1/admin/reconciliation/imports/{id}`
- `POST /api/core/v1/admin/reconciliation/imports/{id}/parse`
- `POST /api/core/v1/admin/reconciliation/imports/{id}/match`
- `POST /api/core/v1/admin/reconciliation/transactions/{tx_id}/apply`
- `POST /api/core/v1/admin/reconciliation/transactions/{tx_id}/ignore`

### Payout queue
- `GET /api/core/v1/admin/finance/payouts`
- `GET /api/core/v1/admin/finance/payouts/{payout_id}`
- `POST /api/core/v1/admin/finance/payouts/{payout_id}/approve`
- `POST /api/core/v1/admin/finance/payouts/{payout_id}/reject`
- `POST /api/core/v1/admin/finance/payouts/{payout_id}/mark-paid`

## Permissions matrix

| Role | Read | Write |
| --- | --- | --- |
| FINANCE | ✅ | ✅ |
| OPS | ✅ | ❌ |
| SUPERADMIN | ✅ | ✅ |
| SALES | ❌ | ❌ |

## Manual verification steps

### Approve payment intake
1. Open **Admin → Finance → Payment intakes**.
2. Select an intake with status `SUBMITTED` or `UNDER_REVIEW`.
3. Click **Approve**, enter a reason, confirm.
4. Verify:
   - Intake status becomes `APPROVED`.
   - Invoice status becomes `PAID`.
   - Subscription status becomes `ACTIVE`.
   - Audit event recorded.

### Apply reconciliation transaction
1. Open **Admin → Finance → Reconciliation imports**.
2. Open an import and locate an `UNMATCHED` transaction.
3. Enter an invoice ID, click **Apply**, enter a reason, confirm.
4. Verify:
   - Transaction status becomes `MATCHED`.
   - Payment intake is created and invoice status is `PAID`.
   - Audit event recorded.

### Approve payout
1. Open **Admin → Finance → Payout queue**.
2. Select a `REQUESTED` payout.
3. Click **Approve**, enter a reason, confirm.
4. Verify:
   - Status becomes `APPROVED`.
   - Ledger/balances updated.
   - Audit event recorded.

## Expected audit events
- `INVOICE_MARKED_PAID`
- `INVOICE_VOIDED`
- `INVOICE_MARKED_OVERDUE`
- `PAYMENT_INTAKE_APPROVED`
- `PAYMENT_INTAKE_REJECTED`
- `reconciliation_manual_applied`
- `reconciliation_ignored`
- `bank_statement_parsed`
- `bank_statement_matched`
- `PAYOUT_APPROVED`
- `PAYOUT_REJECTED`
- `PAYOUT_MARKED_PAID`

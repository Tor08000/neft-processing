# Accounting Exports SLA

## SLA settings
Configured via environment variables:
- `ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES` (default `10`)
- `ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS` (default `48`)

## What is monitored
The scheduler/task `accounting_exports.check_overdue_batches` checks:
- **CREATED** batches that remain ungenerated longer than `ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES`.
- **GENERATED / UPLOADED / DOWNLOADED** batches not confirmed within `ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS`.

For each breach:
- Audit event: `ACCOUNTING_EXPORT_SLA_BREACH`
- Metrics incremented:
  - `core_api_accounting_export_overdue_total`
  - `core_api_accounting_export_unconfirmed_total`

## Operational response
1. Inspect audit logs for `ACCOUNTING_EXPORT_SLA_BREACH` with batch details.
2. Verify the batch status in `/v1/admin/accounting/exports`.
3. Re-run generation if a batch is stuck in `CREATED`.
4. Coordinate with ERP operator to confirm or reject overdue batches.

## Metrics
Available on `/metrics`:
- `core_api_accounting_export_overdue_total`
- `core_api_accounting_export_unconfirmed_total`

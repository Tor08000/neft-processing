# Billing Runbook

## Incident: Invoice issue fails
**Symptoms**
- Alert: `billing_command_errors` or sustained increase in `billing_command_errors_total{command="issue"}`.
- Elevated failures in `billing_invoices_issued_total` vs expected volume.

**Checks**
- Verify command request payloads and validation errors in logs.
- Inspect invoice tables for recent failed/partial records.
- Confirm ledger posting for the invoice transaction (double-entry created).

**Actions**
- Temporarily block invoice issue command at the edge (feature flag / command gate).
- Re-run issue for known failed invoices once root cause is fixed.
- If financial state diverged, create a compensating ledger adjustment.

**Recovery verification**
- `billing_invoices_issued_total` resumes expected rate.
- No new `billing_command_errors_total{command="issue"}` spikes.
- Ledger entries balanced for affected invoice IDs.

## Incident: Payment capture fails
**Symptoms**
- Alert: `billing_command_errors` or sustained increase in `billing_command_errors_total{command="capture"}`.
- Payments not reflected in ledger or payment status remains pending.

**Checks**
- Verify payment provider responses and timeout errors.
- Confirm ledger transaction for capture exists and balances.
- Check payment status table for stuck captures.

**Actions**
- Temporarily block capture command to stop cascading failures.
- Retry capture only for idempotent-safe payment references.
- If capture was processed externally but not posted, create a ledger adjustment.

**Recovery verification**
- Capture success rate returns to SLO.
- Pending captures drain to zero.
- Ledger totals match provider settlement totals.

<a id="ledger-invariant"></a>
## Incident: Ledger invariant violation
**Symptoms**
- Alert: `ledger_invariant_violation` (P1).
- `ledger_invariant_violations_total > 0`.

**Checks**
- Identify the failing transaction ID and accounts impacted.
- Validate double-entry rows for the transaction (debit/credit equality).
- Inspect recent adjustments or backfills around the incident time.

**Actions**
- Immediately block all financial commands (issue/capture/refund).
- Roll back the inconsistent transaction via compensating ledger adjustment.
- Re-run affected commands only after integrity is restored.

**Recovery verification**
- `ledger_invariant_violations_total` stable at 0.
- Integrity checks pass for recent transactions.
- Billing commands re-enabled and operating within SLO.

## Related alerts
- ledger_invariant_violation → billing.md#ledger-invariant

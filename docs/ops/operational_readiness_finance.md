# Operational Readiness v1 — Billing, Reconciliation, Settlement

## Scope
Operational readiness for the financial contour (Billing / Reconciliation / Settlement). No new business features.

## Metrics (AS-IS → SLO-ready)
### Billing / Ledger
**Counters**
- `billing_invoices_issued_total`
- `billing_payments_captured_total`
- `billing_refunds_total`
- `ledger_transactions_total`
- `ledger_adjustments_total`

**Errors**
- `billing_command_errors_total{command="issue|capture|refund"}`
- `ledger_invariant_violations_total`

### Reconciliation
**Counters**
- `reconciliation_runs_total{scope="internal|external",status}`
- `reconciliation_discrepancies_total{type,status}`
- `reconciliation_links_total{status="pending|matched|mismatched"}`

**Gauges**
- `reconciliation_pending_links`
- `reconciliation_open_discrepancies`

### Settlement
- `settlement_periods_total{status}`
- `payouts_total{status}`
- `payout_errors_total`

## Alerts (rules)
### Critical (Pager)
- **ledger_invariant_violation (P1)**
  - Trigger: `ledger_invariant_violations_total > 0`
  - Meaning: Double-entry broken → stop all operations.
- **payout_failed (P1)**
  - Trigger: `payouts_total{status="FAILED"} > 0`

### High (Ops)
- **reconciliation_mismatch (P2)**
  - Trigger: `reconciliation_links_total{status="mismatched"} > N`
  - Notes: `N` is configurable (default suggestion: 5).
- **reconciliation_backlog (P2)**
  - Trigger: `reconciliation_pending_links > threshold for > X hours`

### Medium (Monitor)
- **billing_command_errors (P3)**
  - Trigger: `billing_command_errors_total` is increasing.
- **settlement_stuck (P3)**
  - Trigger: `settlement_periods_total{status="APPROVED"}` without payout for > X hours.

## SLO
### Billing
- **Invoice issue success rate:** ≥ 99.9%
- **Payment capture success rate:** ≥ 99.5%
- **Refund processing latency (p95):** ≤ 2s

### Reconciliation
- **Internal reconciliation completion (p95):** ≤ 5 min
- **External reconciliation delay:** ≤ 24h (business SLO)
- **Mismatch resolution time:**
  - **P1:** ≤ 4h
  - **P2:** ≤ 24h

### Settlement
- **Settlement calculation success:** ≥ 99.9%
- **Payout initiation latency:** ≤ 10 min after approval
- **Payout confirmation window:** ≤ T+1 (stub)

## Dashboard spec (Grafana)
### Billing health
- Issue/capture/refund rates by command (counters + rate)
- Billing command error rate by command
- Ledger transactions vs adjustments volume
- Ledger invariant violations (single stat + alert banner)

### Reconciliation health
- Runs by scope/status (stacked)
- Discrepancies by type/status
- Pending links (gauge + trend)
- Mismatched links (single stat + list)

### Settlement health
- Settlement periods by status
- Payouts by status
- Payout errors (rate)
- Approved → payout latency (p95)

## Notes
- Alert thresholds (`N`, `X`) are configuration values per environment.
- SLO tracking uses Prometheus percentiles for latency and error ratios.

# MoR Ops Alerts + Grafana (Sprint G1)

This document defines the **minimum** alerting and dashboard scope required
for MoR production readiness.

## Required metrics

| Domain | Metric (Prometheus) | Notes |
| --- | --- | --- |
| Settlement | `core_api_mor_settlement_immutable_violation_total` | Settlement snapshot mutated after finalize. |
| Settlement | `core_api_mor_settlement_override_total` | Admin override count. |
| Payout | `core_api_mor_payout_blocked_total{reason=...}` | Payout blocked by reason. |
| Payout | `core_api_mor_payout_failed_total` | Payout batch failed. |
| Payout | `core_api_mor_payout_pending_over_threshold` | Pending payout batches over threshold. |
| Ledger | `core_api_mor_partner_ledger_negative_balance_total` | Negative available balance. |
| Ledger | `core_api_mor_clawback_required_total` | Clawback required after penalty. |
| Revenue | `core_api_mor_platform_fee_mismatch_total` | Platform fee drift vs settlement. |

## Alert rules (minimum)

| Alert | Condition | Severity |
| --- | --- | --- |
| Settlement mutated | `core_api_mor_settlement_immutable_violation_total > 0` | CRITICAL |
| Payout before finalize | `core_api_mor_payout_blocked_total{reason="NO_SNAPSHOT"} > 0` (or `NOT_FINALIZED` if emitted) | HIGH |
| Ledger negative | `core_api_mor_partner_ledger_negative_balance_total > 0` | HIGH |
| Revenue drift | `core_api_mor_platform_fee_mismatch_total > 0` | CRITICAL |

> Alerts must fire on a forced fault in staging before enabling in production.

## Grafana dashboard: MoR Ops

Dashboard panels:

- **Settlement health**: finalized vs open settlement items, immutable violations.
- **Payout queue**: payout batches by state + pending over threshold.
- **Partner balances**: available balance distribution + negative balance count.
- **Overrides timeline**: admin overrides over time (audit + metric).

**Definition of done**

- Alerts fire on forced fault.
- Dashboard is readable in under 30 seconds by on-call.

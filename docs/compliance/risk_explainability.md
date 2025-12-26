# Risk Explainability (Compliance)

## Purpose
risk_decision records are immutable artifacts that explain why a financial or document action was allowed, escalated, or blocked. They are stored for audit trail, legal review, and compliance reporting.

## Required structure for BLOCK / REVIEW
```json
{
  "decision": "BLOCK",
  "score": 92,
  "thresholds": {
    "block": 80,
    "review": 60
  },
  "policy": "HIGH_RISK_PAYOUT",
  "factors": [
    "client_age < 30 days",
    "amount > P95",
    "velocity spike"
  ],
  "model": {
    "name": "risk_v4",
    "version": "2025.01"
  }
}
```

## Storage
- Tables: `risk_decisions`, `decision_results`, `risk_training_snapshots`
- Immutable: updates/deletes are blocked at the ORM layer.
- Linked to audit log via `audit_id`.
- Threshold provenance stored as `risk_policy` and `risk_threshold_set` identifiers in the decision payload.

## Explainability
`top_reasons` are captured from the scoring/rules output and stored in `risk_decisions.reasons`. The full input snapshot is persisted as `features_snapshot` for audit reconstruction.
The explain payload in `decision_results.explain` always includes decision, score, thresholds, policy label, factors, and model metadata.

## Usage
Risk decisions are used by:
- Audit logs
- Admin UI
- Legal/compliance reporting

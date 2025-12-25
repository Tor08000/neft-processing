# Risk Explainability (Compliance)

## Purpose
Risk decisions are immutable records that explain why a financial or document action was allowed, escalated, or blocked. They are stored for audit trail, legal review, and compliance reporting.

## Required structure for BLOCK / ESCALATE
```json
{
  "decision": "BLOCK",
  "risk_level": "VERY_HIGH",
  "score": 92,
  "top_reasons": [
    {"feature": "amount", "impact": 0.42},
    {"feature": "frequency_24h", "impact": 0.31},
    {"feature": "provider_risk", "impact": 0.19}
  ],
  "policy": "payments_ru_v3",
  "model": "risk_model_v3.2"
}
```

## Storage
- Table: `risk_decisions`
- Immutable: updates/deletes are blocked at the ORM layer.
- Linked to audit log via `audit_id`.

## Explainability
`top_reasons` are captured from the scoring/rules output and stored in `risk_decisions.reasons`. The full input snapshot is persisted as `features_snapshot` for audit reconstruction.

## Usage
Risk decisions are used by:
- Audit logs
- Admin UI
- Legal/compliance reporting

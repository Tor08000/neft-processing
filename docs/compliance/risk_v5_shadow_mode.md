# Risk v5 Shadow Mode Compliance Notes

**v4 is frozen baseline; v5 runs in shadow by default.**

## What Shadow Mode Means
- v5 receives the same decision context snapshot as v4.
- v5 computes score, model version, and explainability payload via AI service.
- v5 output never affects production outcomes in v5.0.

## Data Retention
Shadow outputs are persisted in `risk_v5_shadow_decisions` for auditability and retraining datasets. Stored fields include:
- v4 outcome, policy, threshold set, and score
- v5 score and predicted outcome
- features snapshot + hash + schema version
- explain payload with top features and impacts
- provider payload evidence (`schema`, `document_type`, `metadata_keys`, amount presence) so shadow scoring can be replayed against the AI service contract

The v5 shadow scorer maps decision-context features into the AI service `/api/v1/risk-score` contract. The AI service remains a heuristic scoring provider in this repo; it accepts risk subjects such as `payment`, `export`, and `fuel_transaction` explicitly and returns a stable trace hash. Provider failures remain degraded shadow records and never alter v4 outcomes.

## Separation from v4
All v4 thresholds, policies, and explain payloads remain unchanged.

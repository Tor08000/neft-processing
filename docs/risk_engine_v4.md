# Risk Engine v4

## Principles
- Rule-first + model-assisted.
- Final decision is made by policy + thresholds.
- ML acts as a signal; it never decides alone.

## Threshold Sets
`risk_threshold_sets` now provide business-realistic thresholds:

- `scope`: `GLOBAL | TENANT | CLIENT`
- `action`: `PAYMENT | INVOICE | PAYOUT | EXPORT | DOCUMENT_FINALIZE`
- `block_threshold`, `review_threshold`, `allow_threshold`
- `currency` (optional), `valid_from`, `valid_to`, `created_by`

Defaults are global; tenant and client policies can override by selecting a different threshold set.

## Explainability
Every decision emits an explain payload with decision, score, thresholds, policy label, factors, and model metadata.
Explain payloads are persisted in `decision_results.explain`.

## Training pipeline (initial)
Training-ready snapshots are captured in `risk_training_snapshots`:
- decision context + immutable feature vector
- policy and thresholds applied
- score + final outcome
- feature hash + version

Retraining is manual-only and batch/offline.

## Enforcement points
Risk evaluation is enforced on:
- PAYMENT execution
- PAYOUT execution
- INVOICE finalize
- DOCUMENT finalize
- ACCOUNTING EXPORT confirm

BLOCK outcomes prevent final actions; REVIEW outcomes require manual handling.

## Reference status
Risk Engine v4 is a frozen reference implementation. Any changes require a new major version.

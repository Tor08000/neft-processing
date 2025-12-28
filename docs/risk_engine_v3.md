# Risk Engine v3

## Goal
Risk Engine v3 turns risk scoring into real decisions, using **rule-first + model-assisted** execution with audit-grade explainability. It adds:

- **risk_threshold_set**: versioned score-to-decision mappings per subject type.
- **risk_policy**: contextual selection by tenant/client/provider/currency/country with priority.
- **risk_decision**: immutable, auditable records tied to business actions.
- **Model versioning**: training/activation with explicit version identifiers.

## Core flow
1. Hard rules run first (fail fast).
2. Model-assisted scoring runs when no hard block exists.
3. A policy is selected by subject/context.
4. A threshold is selected by score (min/max window).
5. A risk_decision is produced and persisted.
6. The decision outcome gates the business action.

## Entities
- **risk_threshold_set**: versioned, active set of thresholds.
- **risk_policy**: selects a threshold set and model selector.
- **risk_threshold**: maps score ranges to decisions.
- **risk_decision**: immutable record stored for audit/compliance.

## Decision mapping
| Threshold decision | requires_manual_review | risk_decision | Outcome |
| --- | --- | --- | --- |
| ALLOW | false | ALLOW | ALLOW |
| ALLOW | true | ALLOW_WITH_REVIEW | ALLOW (flagged) |
| ESCALATE | n/a | ESCALATE | MANUAL_REVIEW (manual confirmation) |
| BLOCK | n/a | BLOCK | DECLINE |

## API
AI retraining and activation endpoints:

- `POST /admin/ai/train-model`
- `POST /admin/ai/update-model`
- `POST /admin/ai/models/train`
- `POST /admin/ai/models/activate`

## Notes
- Decisions are immutable and appended to the audit log.
- Policies and thresholds are stored in the core database, not hard-coded.
- Hard rules always override model-assisted thresholds.

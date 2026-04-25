# Risk Decisions (Compliance)

## Scope
`risk_decision` records are immutable compliance artifacts produced by the decision_engine.

## Data sources
- `risk_policy` selects the active `risk_threshold_set`.
- `risk_threshold` defines the decision boundary for a score (legacy).
- `risk_threshold_set` also stores v4 block/review/allow thresholds by scope and action.
- The decision_engine persists `risk_decision` rows with score, risk_level, outcome, and reasons.

## Storage & immutability
- Table: `risk_decisions` (core-api).
- ORM guards prevent updates/deletes (`app/models/risk_decision.py`).
- Audit linkage via `audit_id` records an event for every decision.
- `risk_decisions.features_snapshot.audit` stores both decision-level and risk-decision-level audit ids/hashes when persistence is available.
- `risk_decisions.features_snapshot.graph` stores legal graph write status and link identifiers when the subject type has a graph node owner; unsupported subject types are explicit rather than silently ignored.

## Required fields
- `subject_type` / `subject_id`
- `score` + `risk_level`
- `outcome` (`ALLOW/ALLOW_WITH_REVIEW/BLOCK/ESCALATE`)
- `threshold_set_id` + `policy_id`
- `reasons` and `features_snapshot` for explainability
- `risk_training_snapshots` provide immutable training-ready captures of context, thresholds, and outcomes.

## Audit expectations
- Event types: `RISK_DECISION_MADE`, `RISK_DECISION_BLOCKED`, `RISK_DECISION_ESCALATED`.
- Public reporting uses the same `risk_decision` identifiers to ensure traceability.
- Provider-assisted risk payloads must keep source and reproducibility explicit: the current `ai-service` scorer identifies itself as `heuristic_rules` / `local_heuristic` and returns a stable trace hash; the legacy `risk_adapter` adds `decision_trace_hash` to its flags while excluding volatile latency from that hash.
- If the DecisionEngine falls back to its default scorer, the explain payload must mark it as the `decision_engine_default_scorer` compatibility tail with the configured default score and `not_ml=true`; this preserves existing outcome semantics while making the limitation auditable.
- Persisted explain linkage (`record_refs`, audit hashes, legal graph ids) is not part of `decision_hash`; it is used to navigate runtime evidence without changing replay reproducibility.

## What happens when BLOCK
- **Where the block is enforced:** the decision_engine returns `BLOCK`, and the calling workflow (payment, payout, document finalize) halts before executing the final action.
- **Override:** only authorized administrators may override by re-running the action after policy/legal review; overrides are not automatic.
- **What is logged:** a `RISK_DECISION_BLOCKED` audit event is written, including decision id, subject, score, thresholds, and policy identifiers; the explain payload is persisted in `decision_results.explain`.
- **What the client sees:** a blocked action returns a domain error (HTTP 403 for API actions or a risk decline code for domain workflows) without internal rule details.
- **What the administrator sees:** admin UI and audit tools show the full explain payload, reason codes, and linked audit entry.
- **Legal statement:** risk-based blocking is an automated compliance control; decisions are immutable, auditable, and enforce regulatory and contractual obligations.

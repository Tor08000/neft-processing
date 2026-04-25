# ADR-0010 AI / Risk / Explain Owner Truth

## Context

AI/risk contour in repo had three different decision surfaces at once:

- `platform/processing-core/app/services/risk_adapter.py` as legacy rules + AI scorer bridge for transaction authorization.
- `platform/processing-core/app/services/decision/*` as canonical deterministic decision owner for critical payment/document/payout/export actions.
- `platform/processing-core/app/services/risk_v5/*` as shadow scorer and retraining contour.

At the same time `platform/ai-services/risk-scorer` exposed heuristic scoring endpoints that looked like trained-model inference by default, and marketplace compatibility recommendations still carried an `_ml_stub_recommendations()` path.

This created three kinds of runtime drift:

- fake scoring truth (`auto-train`, default metrics, default score `0`, stub-default scoring without explicit assumptions)
- silent fallback (`risk_adapter` timeout/bad-status/malformed payload collapsing into ordinary rules fallback)
- weak explain reproducibility (decision hash/context hash not consistently tied to persisted decision artifacts)

## Decision

- Canonical decision owner for business decisions is `processing-core` deterministic `DecisionEngine`.
- `ai-service` is a scoring provider surface only. In current repo it is a heuristic scorer, not a trained-model owner.
- `risk_adapter` remains a legacy compatibility bridge for transaction risk evaluation, but degraded AI behavior must be explicit in payloads and traces.
- `risk_v5` remains a shadow/evidence contour only. It must never mutate v4 decision semantics and must persist explicit degraded shadow failures.
- Marketplace recommendation compatibility surface must not pretend to support ML mode when no model exists.

## Rules

- No scoring path may invent a missing score with silent defaults.
- No model registry path may fabricate training metrics by default.
- Any degraded scorer/provider response must surface:
  - explicit degraded state
  - error type
  - retryability when known
  - assumptions/source in explain or payload
- Deterministic explain payload must remain reproducible across identical inputs.
- Runtime storage links (`record_refs`, audit ids/hashes, legal graph ids/status) may be attached to persisted explain artifacts, but they are excluded from `decision_hash`; `decision_hash` remains input/rule/threshold/model-derived.
- Heuristic scorer responses must expose a stable decision trace and SHA-256 trace hash over non-volatile inputs, ruleset/formula version, score breakdown, thresholds, result, and assumptions.
- Audit/graph linkage belongs to persisted decision artifacts; explain payloads remain deterministic and input-derived.

## Resulting owner split

- `platform/processing-core/app/services/decision/*`
  - owner of decision pipeline: input -> context -> rules -> score -> decision -> explain -> audit
  - default scorer remains a compatibility tail only; when used it must expose `compatibility_tail=decision_engine_default_scorer`, `default_score`, `not_ml`, assumptions, and trace hash
- `platform/processing-core/app/services/risk_rules.py`
  - owner of legacy deterministic rules DSL/runtime for operation risk
- `platform/processing-core/app/services/risk_adapter.py`
  - compatibility bridge between legacy rules and external/AI scorer
- `platform/ai-services/risk-scorer`
  - heuristic scoring provider with explicit `source/assumptions/degraded` semantics
- `platform/processing-core/app/services/risk_v5/*`
  - shadow scoring, feature snapshots, AB/retraining evidence only
- `platform/processing-core/app/services/explain/*`
  - read-side explain aggregation over persisted domain evidence

## Consequences

- Heuristic scoring is still allowed, but it must identify itself as heuristic rather than implied ML.
- Missing ML wiring is represented as explicit degraded/unsupported state, not silent fallback.
- Decision reproducibility now relies on:
  - deterministic explain payload with `decision_hash`
  - persisted `context_hash`
  - `risk_decisions.features_snapshot` carrying decision/evidence linkage, storage refs, audit hashes, and legal graph write status
  - `ai-service` risk-score `explain.trace_hash` and legacy `/api/v1/score` `trace.trace_hash`
  - `risk_adapter.flags.decision_trace_hash` with volatile provider latency excluded from the hash
  - `risk_v5` shadow scorer payloads mapped to the AI service `risk-score` contract with explicit provider payload evidence
- Compatibility tails remain:
  - legacy `risk_adapter`
  - marketplace compatibility recommendation route in `client_marketplace`
  - risk_v5 shadow mode

They are intentional compatibility/evidence contours, not product-owner ambiguity.

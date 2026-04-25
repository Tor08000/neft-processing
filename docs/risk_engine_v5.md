# Risk Engine v5 (Shadow Mode)

**v4 is frozen baseline; v5 runs in shadow by default.**

## Overview
Risk Engine v5 introduces ML-heavy scoring, shadow mode execution, deterministic A/B policies, and retraining scaffolding while keeping v4 untouched.

## Scope (v5.0)
- Shadow scoring with persisted feature snapshots and explainability payloads.
- Deterministic A/B assignment (Mode 1: v4 decides, v5 scores for bucket B).
- Model registry selector (`risk_v5_<subject_type>`) for activation workflows.
- Retraining pipeline scaffolding with quality gates (manual activation).
- Drift metrics snapshot for score distribution monitoring.

## Key Components
- `platform/processing-core/app/services/risk_v5/` — v5 orchestration, shadow scorer, A/B policy logic.
- `risk_v5_shadow_decisions` table — persisted v5 shadow output.
- `risk_v5_ab_assignments` table — optional A/B overrides.
- `risk_v5_labels` table — unified labels from overrides and outcomes.

## Scoring
v5 calls the existing AI service `/api/v1/risk-score` endpoint using the selector `risk_v5_<subject_type>`.
The shadow adapter maps v4 decision-context features into that provider contract and stores provider payload evidence with every shadow explain. The AI service is still a heuristic provider in this repo, not a trained-model owner; its response must include stable trace data and the shadow record must remain degraded if the provider rejects the payload.

## Configuration
- `RISK_V5_SHADOW_ENABLED` controls whether shadow hooks are active (default: `false`).
- `RISK_V5_AB_WEIGHT` controls share of bucket **B** (default: `50`).

## Rollout
v5 is isolated to shadow mode and can be safely rolled back without affecting v4 outcomes.

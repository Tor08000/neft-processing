# Risk v5 Retraining Operations

**v4 is frozen baseline; v5 runs in shadow by default.**

## Pipeline Stages (v5.0)
1. **Dataset build** from `risk_v5_shadow_decisions` joined with `risk_v5_labels`.
2. **Train** (LightGBM/XGBoost placeholder in v5.0).
3. **Validate** with AUC/precision gates.
4. **Publish** to registry as `CANDIDATE` (manual activation).

## Manual Run
Use the admin endpoint:
```
POST /v1/admin/risk-v5/retraining/run
```

The endpoint currently runs a scaffolded pipeline and returns the candidate model version if published.

## Quality Gates
- AUC must exceed baseline threshold.
- Precision minimum for high-risk decisions.
- Drift checks (score distribution stability).

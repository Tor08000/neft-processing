# Risk v5 A/B Policies

**v4 is frozen baseline; v5 runs in shadow by default.**

## Deterministic Bucketing
Bucket assignment is deterministic per client and subject type:
```
bucket = sha256(client_id + subject_type + salt) % 100
```
- `0..(weight_b-1)` → **B** (v5 shadow scoring)
- `weight_b..99` → **A** (v4 only)

Configure with `RISK_V5_AB_WEIGHT` to control the B share.

## Shadow AB (v5.0)
Mode 1 is enabled:
- v4 produces the final decision.
- v5 scores in the background for bucket **B** only.

## Overrides
Use the admin endpoint to create an explicit assignment:
```
POST /v1/admin/risk-v5/ab/assignments
```
Assignments are evaluated with client-level overrides taking precedence over tenant-level, then global defaults.

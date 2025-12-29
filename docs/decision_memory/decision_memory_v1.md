# Decision Memory v1 (No-ML)

## Purpose
Decision Memory stores facts about applied actions, their measured effects, and provides deterministic decay, cooldown, and explanation logic. It does **not** train models or auto-apply actions.

## Data Model
### decision_outcomes
Stores one record per applied action + measured effect.

Key fields:
- `tenant_id`, `client_id`
- `entity_type`: DRIVER, VEHICLE, STATION, CLIENT
- `entity_id`
- `insight_id`, `applied_action_id`
- `action_code`, `bundle_code`
- `applied_at`, `measured_at`, `window_days`
- `effect_label`: IMPROVED, NO_CHANGE, WORSE, UNKNOWN
- `effect_delta` (JSON)
- `confidence_at_apply` (optional)
- `context` (primary reason, insight type, etc.)

Idempotency is enforced with:
- Unique `applied_action_id`.
- Unique index on `(tenant_id, entity_type, entity_id, action_code, applied_at::date)`.

### decision_action_stats_daily
Daily aggregate per action/entity type for fast rollups.

Key fields:
- `tenant_id`, `client_id` (optional)
- `action_code`, `entity_type`, `day`
- `applied_count`, `improved_count`, `no_change_count`, `worse_count`
- `weighted_success`

## Decay
Weighted success is computed at query time using a half-life decay:

```
w = 0.5 ** (age_days / HALF_LIFE_DAYS)
weighted_success += w * improved_flag
```

Defaults:
- `MEMORY_WINDOW_DAYS = 90`
- `HALF_LIFE_DAYS = 30`
- `MIN_SAMPLE_SIZE = 5`

## Cooldown / Avoid Repeats
For a given entity and action:
- If applied `MAX_REPEAT` times in `COOLDOWN_DAYS` and
- `NO_CHANGE/WORSE` occurs `MAX_FAILED_STREAK` times in a row,

then the action is placed on cooldown.

Defaults:
- `COOLDOWN_DAYS = 14`
- `MAX_REPEAT = 2`
- `MAX_FAILED_STREAK = 2`

Cooldown output example:

```json
{
  "cooldown": true,
  "reason": "Action tried 2 times in 14 days with no improvement"
}
```

## Integrations
- **Effect measurement hook**: when `fi_action_effects` are recorded, a `decision_outcome` is stored.
- **Decision Choice**: cooldown applies a penalty, low sample sizes are marked, and memory stats are added to explanations.
- **Projection**: if cooldown is active, expected effect is downgraded and warnings are returned.
- **Unified Explain**: includes `decision_memory` with last actions and cooldown status.

## Admin API (read-only)
- `GET /admin/decision-memory/outcomes?entity_type=&entity_id=`
- `GET /admin/decision-memory/stats?action_code=&window_days=90`
- `GET /admin/decision-memory/cooldown?entity_type=&entity_id=&action_code=`

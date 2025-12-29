# Fleet Policies v4.1 — Scenario Bundles

## Overview

Scenario bundles group multiple actions into a single policy playbook. One trigger maps to a bundle that includes:

- A user-visible title and duration
- Trigger conditions
- Ordered steps (actions + parameters)
- Success criteria

Bundles are suggestions only; they are not auto-applied.

## Bundle schema

```yaml
bundle_code: DRIVER_RISK_HIGH_14D
title: "Снижение риска водителя на 14 дней"
duration_days: 14
triggers:
  - insight_type: DRIVER_BEHAVIOR_DEGRADING
    severity: HIGH
steps:
  - action: SUGGEST_RESTRICT_NIGHT_FUELING
    params: { window: "23:00-06:00" }
  - action: SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL
    params: { required: true }
  - action: SUGGEST_LIMIT_PROFILE_SAFE
    params: { priority: "HIGH" }
success_criteria:
  - metric: driver_score
    delta: -10
```

## Explain payload

Unified Explain includes the matched bundle under `fleet_policy_bundle`:

```json
{
  "bundle_code": "DRIVER_RISK_HIGH_14D",
  "title": "Снижение риска водителя на 14 дней",
  "duration_days": 14,
  "steps": [
    {"action": "SUGGEST_RESTRICT_NIGHT_FUELING", "params": {"window": "23:00-06:00"}},
    {"action": "SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL", "params": {"required": true}},
    {"action": "SUGGEST_LIMIT_PROFILE_SAFE", "params": {"priority": "HIGH"}}
  ],
  "success_criteria": [{"metric": "driver_score", "delta": -10}]
}
```

Suggested actions created from bundles include `bundle_code`, `step_index`, and `params` in the action payload.

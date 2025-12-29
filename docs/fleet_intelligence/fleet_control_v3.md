# Fleet Intelligence v3 — Fleet Control

## Overview
Fleet Control v3 stores actionable insights generated from Fleet Intelligence trends, provides suggested actions for ops, and captures action effects.

## Lifecycle
- Insights are created from degrading trends.
- Suggested actions are generated deterministically per policy mapping.
- Actions require admin approval and reason codes before execution.
- Apply is executed via admin endpoints only.
- Applied actions enter monitoring and are evaluated after 7 days.

## Admin API
- `GET /v1/admin/fleet-control/insights`
- `GET /v1/admin/fleet-control/insights/{id}`
- `POST /v1/admin/fleet-control/actions/{id}/approve`
- `POST /v1/admin/fleet-control/actions/{id}/apply`

## Control Loop
1. Nightly task generates insights from v2 trends.
2. Policies map insights to suggested actions.
3. Ops approves and applies actions via admin endpoints (reason required).
4. Monitoring job measures effects and labels outcomes.

## Unified Explain
`fleet_control` section includes:
- Active insight status
- Suggested actions
- Last applied action summary
- Effect label (if measured)

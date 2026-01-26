# /api/core/portal/me Contract

## Purpose
`/api/core/portal/me` is the single source of truth (SSoT) for portal access state. Frontends **must not** re-compute onboarding, subscription, or access logic locally. They should only render based on `access_state` and `access_reason`.

## Response schema (contracted fields)

```json
{
  "actor_type": "client|partner|admin",
  "user": {
    "id": "string",
    "email": "string|null",
    "subject_type": "string|null",
    "timezone": "string|null"
  },
  "org": {
    "id": "string",
    "name": "string|null",
    "inn": "string|null",
    "status": "string|null",
    "timezone": "string|null"
  },
  "org_status": "string|null",
  "org_roles": ["string"],
  "user_roles": ["string"],
  "scopes": ["string"] | null,
  "flags": { "accepted_legal": true } | null,
  "legal": {
    "required_count": 0,
    "accepted": true,
    "missing": ["string"],
    "required_enabled": true
  } | null,
  "features": {
    "onboarding_enabled": true,
    "legal_gate_enabled": true
  } | null,
  "subscription": {
    "plan_code": "string|null",
    "status": "string|null",
    "billing_cycle": "string|null",
    "support_plan": "string|null",
    "slo_tier": "string|null",
    "addons": [{"any": "value"}] | null
  } | null,
  "entitlements_snapshot": { "any": "value" } | null,
  "capabilities": ["string"],
  "nav_sections": [{ "code": "string", "label": "string" }] | null,
  "partner": {
    "status": "string|null",
    "profile": {
      "display_name": "string|null",
      "contacts_json": { "any": "value" } | null,
      "meta_json": { "any": "value" } | null
    } | null
  } | null,
  "access_state": "AUTH_REQUIRED|NEEDS_ONBOARDING|NEEDS_PLAN|NEEDS_CONTRACT|ACTIVE|OVERDUE|SUSPENDED|LEGAL_PENDING|PAYOUT_BLOCKED|SLA_PENALTY|MODULE_DISABLED|MISSING_CAPABILITY|FORBIDDEN_ROLE|SERVICE_UNAVAILABLE|MISCONFIG|TECH_ERROR",
  "access_reason": "string|null"
}
```

## Access state enum values

- `AUTH_REQUIRED`
- `NEEDS_ONBOARDING`
- `NEEDS_PLAN`
- `NEEDS_CONTRACT`
- `ACTIVE`
- `OVERDUE`
- `SUSPENDED`
- `LEGAL_PENDING`
- `PAYOUT_BLOCKED`
- `SLA_PENALTY`
- `MODULE_DISABLED`
- `MISSING_CAPABILITY`
- `FORBIDDEN_ROLE`
- `SERVICE_UNAVAILABLE`
- `MISCONFIG`
- `TECH_ERROR`

## Deterministic computation inputs

`access_state` and `access_reason` are computed **only** from:

- `org.status`
- `subscription.status`
- onboarding `contract.status` (client)
- `entitlements_snapshot` (modules/features/capabilities)
- `partner.status` / partner finance state (when available)
- `org_roles` and `user_roles`

No hidden or time-based logic is allowed.

## Priority order (highest → lowest)

1. `AUTH_REQUIRED` (no token / unauthenticated)
2. `FORBIDDEN_ROLE`
3. `SERVICE_UNAVAILABLE` / `MISCONFIG` (infra/boot errors)
4. `SUSPENDED`
5. `OVERDUE`
6. `LEGAL_PENDING` / `PAYOUT_BLOCKED` / `SLA_PENALTY` (partner)
7. `NEEDS_ONBOARDING` / `NEEDS_PLAN`
8. `MODULE_DISABLED` / `MISSING_CAPABILITY`
9. `ACTIVE`

The first matching rule wins. For the same inputs, the output must be identical (idempotent and deterministic).

## Condition → state → reason mapping

| Condition (evaluated in priority order) | access_state | access_reason |
| --- | --- | --- |
| No authentication token | AUTH_REQUIRED | auth_required |
| Role does not allow portal access | FORBIDDEN_ROLE | forbidden_role |
| Infrastructure error / portal misconfiguration | SERVICE_UNAVAILABLE / MISCONFIG | service_unavailable / misconfig |
| Subscription status in `SUSPENDED/BLOCKED/PAUSED` | SUSPENDED | billing_suspended |
| Subscription status in `OVERDUE/PAST_DUE/PASTDUE/DELINQUENT` | OVERDUE | billing_overdue |
| Legal gate required and not accepted | LEGAL_PENDING | legal_not_verified |
| Partner payout blocked (when provided) | PAYOUT_BLOCKED | payout_blocked |
| SLA penalty active (when provided) | SLA_PENALTY | sla_penalty |
| Org status is missing or not `ACTIVE` | NEEDS_ONBOARDING | org_not_active |
| Subscription missing or no plan | NEEDS_PLAN | subscription_missing |
| Contract missing or not signed | NEEDS_CONTRACT | contract_missing / contract_not_signed |
| All modules disabled in entitlements snapshot | MODULE_DISABLED | module_disabled |
| Capabilities snapshot is empty | MISSING_CAPABILITY | missing_capability |
| None of the above | ACTIVE | null |

## Backward compatibility

Existing fields (`org_status`, `subscription`, `entitlements_snapshot`, etc.) remain unchanged. `access_state`/`access_reason` are additive and must not break older portals.

## Smoke (Windows CMD)

Use the scripted smoke runner to validate the contract against a running docker stack:

- `scripts/smoke_portal_access_state.cmd`

Or run manually:

```cmd
curl -s -X POST http://localhost/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"client@neft.local\",\"password\":\"client\",\"portal\":\"client\"}"

curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <TOKEN>"
```

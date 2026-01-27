# Portals Quickstart (Client + Partner + Admin)

This runbook gives a single command flow to bring up the stack, seed demo data, validate the three portals, and run the required E2E scenarios. It is designed to keep the UI unblocked by relying on the SSoT endpoints `/api/core/portal/me` (client/partner) and `/api/core/v1/admin/me` (admin), plus required finance/runtime checks.

## Prerequisites

- Docker + Docker Compose
- Python (for JSON parsing in smoke scripts)

## 1) Start the stack

```cmd
docker compose up -d --build
```

## 2) Seed demo data

```cmd
scripts\seed_e2e.cmd
```

> Uses default demo accounts (`client@neft.local`, `partner@neft.local`, `admin@example.com`). Override via `NEFT_BOOTSTRAP_*` or `CLIENT_*/PARTNER_*/ADMIN_*` environment variables if needed.

## 3) Unified portal smoke

This script validates:
- `/client`, `/partner`, `/admin` index + asset build checks
- Login into all three portals
- `/api/core/portal/me` (client + partner)
- `/api/core/v1/admin/me`
- `/api/core/v1/admin/runtime/summary`
- `/api/core/partner/ledger`
- `/api/core/portal/client/dashboard`

```cmd
scripts\smoke_all_portals.cmd
```

## 4) E2E scenarios

### Scenario A — Client new (signup → onboarding → ACTIVE)

```cmd
scripts\smoke_onboarding_e2e.cmd
```

Expected:
- `/api/core/portal/me` drives the UI through `NEEDS_ONBOARDING` → `ACTIVE`.
- Cards/users/docs endpoints respond after activation.

### Scenario B — Partner payout (ledger → payout request → history)

```cmd
scripts\smoke_partner_legal_payout_e2e.cmd
```

Expected:
- Partner ledger is available.
- Payout request flow succeeds after legal checks.

### Scenario C — Admin “why not paid”

```cmd
scripts\smoke_admin_finance.cmd
```

Expected:
- Admin runtime and finance views highlight blocked payouts, invoice statuses, and settlement breakdowns without DB access.

## 5) Troubleshooting

- If a portal returns 401 after login, the UI should land on `AUTH_REQUIRED` and not loop between login and cabinet. Re-run `scripts\smoke_all_portals.cmd` to confirm the token flow.
- Use `scripts\smoke_slice_2_admin_runtime.cmd` for deeper runtime summary inspection.
- Use `scripts\smoke_portal_access_state.cmd` to verify AccessState mapping for client/partner.

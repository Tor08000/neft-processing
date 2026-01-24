# Slice 1: SSoT bootstrap (client + partner + admin)

## Goal
Ensure all three portals read UI state from SSoT endpoints and expose bootstrap fields consistently.

## Endpoints
- `GET /api/core/portal/me` (client + partner)
- `GET /api/core/v1/admin/me` (admin)

## Smoke (Windows CMD)
```cmd
scripts\smoke_slice_1_bootstrap.cmd
```

The script:
- Logs in as client, partner, and admin.
- Fetches `/portal/me` and `/v1/admin/me`.
- Prints `access_state`, `roles`, and `read_only` summary.

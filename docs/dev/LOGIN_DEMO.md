# Demo logins (dev stand)

Use `scripts\seed.cmd` after `docker compose up -d --build`.

## Credentials

- Admin: `admin@neft.local` / `Neft123!`
- Partner: `partner@neft.local` / `Partner123!`
- Client: `client@neft.local` / `Client123!`

Tenant code for login flow: `neft`.

These are seeded dev/smoke accounts, not production secrets. Portal login pages do not expose or prefill demo passwords by default:

- Admin UI shows demo chips only when built with `NEFT_DEMO_LOGIN_ENABLED=true`; set `NEFT_DEMO_ADMIN_EMAIL` and pass `NEFT_DEMO_ADMIN_PASSWORD` through an explicit local compose override or manual build arg for that demo build.
- Client and Partner UI show demo chips only when built with `VITE_DEMO_MODE=true`.
- Production/commercial builds should keep those flags unset or `false` and rely on real user credentials.

## Quick checks

- Seed data: `scripts\seed.cmd`
- Diagnostics: `scripts\doctor.cmd`

`doctor.cmd` validates:

- postgres connectivity
- auth-host DB credentials and connectivity
- `processing_core` schema presence
- demo auth users existence
- minimal demo rows in `processing_core.clients/accounts/partner_accounts/client_users/client_user_roles/partner_user_roles`

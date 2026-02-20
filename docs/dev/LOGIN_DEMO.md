# Demo logins (dev stand)

Use `scripts\seed.cmd` after `docker compose up -d --build`.

## Credentials

- Admin: `admin@example.com` / `Admin123!`
- Partner: `partner@neft.local` / `Partner123!`
- Client: `client@neft.local` / `Client123!`

Tenant code for login flow: `neft`.

## Quick checks

- Seed data: `scripts\seed.cmd`
- Diagnostics: `scripts\doctor.cmd`

`doctor.cmd` validates:

- postgres connectivity
- auth-host DB credentials and connectivity
- `processing_core` schema presence
- demo auth users existence
- minimal demo rows in `processing_core.clients/accounts/partner_accounts/client_users/client_user_roles/partner_user_roles`

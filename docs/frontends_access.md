# Frontend Access And Demo Credential Policy

This page is the operator-facing map for opening the three NEFT portals in local
development and for understanding how seeded demo credentials are exposed.

## Gateway URLs

Current `docker-compose.yml` exposes the SPA portals through `gateway` only:

```text
Admin UI:   http://localhost/admin/
Client UI:  http://localhost/client/
Partner UI: http://localhost/partner/
```

The gateway routes these paths to `admin-web`, `client-web`, and `partner-web`
through `gateway/nginx.conf`.

## Direct Local Vite URLs

When running the Vite dev servers directly, use the ports from each portal's
`vite.config.ts`:

```text
Admin UI dev server:   http://localhost:8080/admin/
Client UI dev server:  http://localhost:4174/client/
Partner UI dev server: http://localhost:4176/partner/
```

The default compose stack does not publish the frontend containers directly on
4173/4174/4175. Use gateway URLs for compose unless an override file explicitly
adds those port mappings.

## Seeded Accounts

Seeded accounts are created for local smoke tests and developer verification.
They are not production secrets and they are not automatic UI demo fallbacks.

```text
Admin
  email:    admin@neft.local
  password: Neft123!

Client
  email:    client@neft.local
  password: Client123!

Partner
  email:    partner@neft.local
  password: Partner123!
```

Runtime source of truth: `platform/auth-host/app/seeds/demo_users.py`.

## UI Exposure Rules

Portal login pages must not expose or prefill demo passwords by default.

- Admin UI shows demo chips only when built with
  `NEFT_DEMO_LOGIN_ENABLED=true`.
- Admin demo login also requires explicit `NEFT_DEMO_ADMIN_EMAIL` and an
  explicit local override/build arg for `NEFT_DEMO_ADMIN_PASSWORD`.
- Client and Partner UI show demo chips only when built with
  `VITE_DEMO_MODE=true`.
- Commercial builds should keep those flags unset or `false`.

The admin Dockerfile defaults `NEFT_DEMO_LOGIN_ENABLED=false` and does not bake
in a default admin password. `docker-compose.yml` does not pass
`NEFT_DEMO_ADMIN_PASSWORD` to the admin UI build, even when the local `.env`
contains the seeded smoke password.

## E2E Overrides

Browser and smoke tests may still use seeded credentials explicitly. Override
them with:

```text
ADMIN_EMAIL / ADMIN_PASSWORD
CLIENT_EMAIL / CLIENT_PASSWORD
PARTNER_EMAIL / PARTNER_PASSWORD
```

Some seed/smoke scripts also support `NEFT_BOOTSTRAP_*` variables for
deterministic account setup. Those variables are for local automation and should
not be treated as frontend UI defaults.

## Base Path Contract

```text
Admin:   VITE_PUBLIC_BASE=/admin/
Client:  VITE_PUBLIC_BASE=/client/
Partner: VITE_PUBLIC_BASE=/partner/
```

All three portals should use `/api` through gateway in compose. Avoid direct
service URLs in browser-facing production builds unless a deployment-specific
gateway contract explicitly requires it.

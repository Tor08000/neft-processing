# Demo users & login (auth-host)

## Where user data and hashing live

* **User model:** `platform/auth-host/app/models/user.py` (dataclass representing DB rows).
* **DB connection/session:** `platform/auth-host/app/db.py` (`get_conn()` yields `psycopg` async connection + cursor).
* **Password hashing/verification:** `platform/auth-host/app/security/__init__.py` (`hash_password`, `verify_password`).

These are the building blocks used by the demo seed and reset CLI.

## Login endpoint

Gateway endpoint:

```
POST /api/auth/v1/auth/login
```

Payload:

```json
{ "email": "...", "password": "..." }
```

## Demo users (seeded)

The seed is deterministic and idempotent; it creates missing users, re-activates existing ones,
syncs roles, and updates passwords to the fixed demo values.

| User | Email | Password | Roles |
| --- | --- | --- | --- |
| Admin | `admin@example.com` | `admin` | `PLATFORM_ADMIN` |
| Client | `client@neft.local` | `client` | `CLIENT_OWNER` |
| Partner | `partner@neft.local` | `partner` | `PARTNER_OWNER` |

> Note: `PARTNER_OWNER` is required by the partner portal role checks. Auth-host stores role codes as strings
> and does not currently validate partner-specific roles in its admin schemas.

## Environment overrides

Demo credentials can be overridden via environment variables (used by the seed/CLI):

* `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_FULL_NAME`
* `CLIENT_EMAIL`, `CLIENT_PASSWORD`, `CLIENT_FULL_NAME`, `CLIENT_UUID`
* `PARTNER_EMAIL`, `PARTNER_PASSWORD`, `PARTNER_FULL_NAME`

These fall back to the existing `NEFT_DEMO_*` / `DEMO_*` environment variables when present.

## CLI reset tool

Run inside the auth-host container:

```bash
python -m app.cli.reset_passwords --demo --force
```

Options:

* `--demo` — reset all demo users listed above.
* `--email <email> --password <password>` — reset a single user.
* `--force` — rewrite the password even if it already matches.

The command prints `created`, `updated`, or `skipped` per user.

## Auto-seeding in dev compose

`docker-compose.yml` enables demo seeding in dev via:

```
DEMO_SEED_ENABLED=1
```

`platform/auth-host/entrypoint.sh` runs the demo reset after migrations if the flag is enabled.

## Smoke test

```bash
curl -i -X POST http://localhost/api/auth/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin"}'
```

# Auth mode for `processing-core`

`processing-core` supports two startup validation modes controlled by `AUTH_HOST_MODE`.

## Modes

- `AUTH_HOST_MODE=external` (default)
  - Auth domain is expected to be owned by `auth-host`.
  - `processing_core.users` is **not** required during core startup table validation.
- `AUTH_HOST_MODE=embedded`
  - Legacy/fallback mode where auth tables live in `processing_core`.
  - `processing_core.users` is required during startup validation.

Deprecated compatibility alias: `NEFT_AUTH_MODE` (used only if `AUTH_HOST_MODE` is not set).

## Required tables checked at startup

Base required tables (always):

- `processing_core.alembic_version_core`
- `processing_core.operations`
- `processing_core.clients`
- `processing_core.client_user_roles`
- `processing_core.cards`
- `processing_core.card_limits`

Embedded-only required tables:

- `processing_core.users`

## Troubleshooting

If startup fails with `required tables missing after migrations`:

1. Check the resolved mode in logs (`AUTH_HOST_MODE=<value>`).
2. For `external` mode, ensure base tables exist and migrations are up-to-date.
3. For `embedded` mode, create/migrate `processing_core.users` as part of embedded auth schema.
4. If the log mentions `users required only for embedded mode`, switch to `AUTH_HOST_MODE=external` when using external auth-host.

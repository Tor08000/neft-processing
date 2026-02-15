# Auth Host Service

## OIDC adapter (Enterprise SSO)

`auth-host` acts as an Identity Gateway:

- redirects users to external OIDC IdP;
- validates callback (`state`, `nonce`, `iss`, `aud`, `exp`, `alg=RS256`, JWKS signature);
- links/creates local user via `oauth_identities`;
- maps external roles via `oidc_role_mappings`;
- issues internal NEFT JWT (`admin` / `client` / `partner` audiences).

### Required ENV (single-tenant)

```bash
OIDC_ENABLED=1
OIDC_PROVIDER_NAME=corp
OIDC_ISSUER=https://idp.company.ru
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
OIDC_REDIRECT_URI=https://api.neft.local/api/v1/auth/oauth/callback
OIDC_SCOPES=openid email profile
OIDC_STATE_SECRET=replace-me
OIDC_DEFAULT_ROLE=CLIENT_OWNER
FORCE_SSO=0
DISABLE_PASSWORD_LOGIN=0
```

### Multi-tenant mode

Configure `oidc_providers` table (and optionally `tenant_id`) and enable provider with `enabled=true`.

### Endpoints

- Start auth: `GET /api/v1/auth/oauth/start?provider=corp&portal=client`
- Callback: `GET /api/v1/auth/oauth/callback?code=...&state=...`

### Role mapping

Use `oidc_role_mappings`:

- `external_role=corp_admin` → `internal_role=ADMIN`
- `external_role=corp_user` → `internal_role=CLIENT_OWNER`

If no mapping found, `OIDC_DEFAULT_ROLE` is assigned.

### Fail-fast in production

If `OIDC_ENABLED=1`, startup validates discovery for enabled providers and fails startup if issuer/discovery are invalid.

## Tests

Run tests from the service directory:

```bash
cd platform/auth-host
pytest -q
```

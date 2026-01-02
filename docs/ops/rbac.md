# RBAC (Roles → Permissions → Guards)

## Roles and permissions

**Roles (canonical)**

- `admin`
- `client_user` (includes `CLIENT_USER`, `CLIENT_OWNER`, `CLIENT_ADMIN`, `CLIENT_ACCOUNTANT`)
- `partner_user` (includes `PARTNER_*`)
- `client_admin` (optional)
- `partner_admin` (optional)

**Permissions (v1)**

Client:
- `client:dashboard:view`
- `client:invoices:list`
- `client:invoices:view`
- `client:invoices:download`
- `client:contracts:list`
- `client:contracts:view`
- `client:sla:view`

Partner:
- `partner:dashboard:view`
- `partner:contracts:list`
- `partner:contracts:view`
- `partner:settlements:list`
- `partner:settlements:view`
- `partner:payouts:list`
- `partner:payouts:confirm`

Admin:
- `admin:contracts:*`
- `admin:billing:*`
- `admin:reconciliation:*`
- `admin:settlement:*`
- `admin:audit:*`

## How roles are issued

Roles come from JWT claims:

- `roles`: list of strings
- `role`: single string
- `subject_type`: `client_user` or `partner_user` (fallback when roles are absent)

Claims are normalized into canonical roles in `app/security/rbac/roles.py`. Existing roles remain valid; the RBAC layer maps them to the canonical set.

## Adding a new permission

1. Add the permission string to `app/security/rbac/permissions.py`.
2. Map it to the appropriate role(s) in `app/security/rbac/roles.py`.
3. Add a guard to the router using `require_permission("...")`.
4. Add ownership enforcement (if applicable) via `app/security/rbac/ownership.py`.
5. Add tests in `app/tests/` to cover the new permission and ownership scope.

## Common errors

- **401 Unauthorized**: missing or invalid token (no `Authorization: Bearer ...`).
- **403 Forbidden**: token present, but missing permission or ownership.

Example response:

```json
{ "error": "forbidden", "reason": "missing_permission", "permission": "client:invoices:view" }
```

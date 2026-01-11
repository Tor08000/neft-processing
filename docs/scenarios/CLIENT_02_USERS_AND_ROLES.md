# CLIENT 02 — Users and Roles Management

## Goal
Allow a client owner/admin to manage client users and their roles.

## Actors & Roles
- Client Owner / Client Admin
- Regular User

## Prerequisites
- Auth-host service (`platform/auth-host`) for user identities.

## UI Flow
**Client portal**
- Users list → create user → assign roles/scopes → disable user.

**NOT IMPLEMENTED**
- Client portal UI for user management is not present.

## API Flow
**NOT IMPLEMENTED**
- No client-facing user management endpoints exist in `platform/processing-core`.
- Auth-host provides admin user CRUD but is not scoped to client membership:
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `GET /v1/auth/me`

## DB Touchpoints
- `auth-host`: `users`, `user_roles`.
- **NOT IMPLEMENTED**: client/user membership tables.

## Events & Audit
- **NOT IMPLEMENTED**: `USER_CREATED`, `USER_ROLE_CHANGED`, `USER_DISABLED` events are not emitted for client user management.

## Security / Gates
- Client RBAC enforcement is handled by token roles/permissions, but no self-service user admin is exposed.

## Failure modes
- Attempt to manage users through client portal → **NOT IMPLEMENTED**.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (no user management API to test).
- smoke cmd: `scripts/smoke_client_users_roles.cmd` (fails with NOT IMPLEMENTED).
- PASS: **NOT IMPLEMENTED**.

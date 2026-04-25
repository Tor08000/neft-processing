# CLIENT 02 - Users and Roles Management

## Goal
Allow a client management actor to bootstrap a new client workspace, list current memberships, invite users, manage invitation lifecycle, and update client role assignments through mounted client-owner routes.

## Actors & Roles
- `CLIENT_OWNER`
- `CLIENT_MANAGER`
- `CLIENT_ADMIN`
- regular client user without management access

## Prerequisites
- `platform/auth-host` for identity bootstrap (`register/login/verify/me`)
- `platform/processing-core` for canonical client controls owner routes

## UI Flow
**Client portal**
- users list -> invite employee -> inspect invitations -> resend/revoke invitation -> update membership roles

## API Flow
- Auth/bootstrap:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/verify`
  - `GET /api/v1/auth/me`
  - `GET /api/core/client/auth/verify`
  - `GET /api/core/portal/me`
- Client controls owner routes:
  - `GET /api/core/client/users`
  - `POST /api/core/client/users/invite`
  - `GET /api/core/client/users/invitations`
  - `POST /api/core/client/users/invitations/{invitation_id}/resend`
  - `POST /api/core/client/users/invitations/{invitation_id}/revoke`
  - `POST /api/core/client/users/{user_id}/roles`
  - `PATCH /api/core/client/users/{user_id}/roles`
  - `DELETE /api/core/client/users/{user_id}`

## DB Touchpoints
- `auth-host`:
  - `users`
  - `user_roles`
  - `user_clients`
- `processing-core`:
  - `clients`
  - `client_onboarding`
  - `client_users`
  - `client_user_roles`
  - `client_invitations`
  - `invitation_email_deliveries`
  - `notification_outbox`
  - `audit_log`

## Events & Audit
- invitation notifications/outbox:
  - `INVITATION_CREATED`
  - `INVITATION_RESENT`
  - `INVITATION_REVOKED`
  - invitation email delivery events
- audit actions:
  - `role_change`
  - `invitation_resend`
  - `invitation_revoke`
  - `user_disable`

## Security / Gates
- client onboarding token required
- management routes are gated by client roles
- `CLIENT_MANAGER` can operate the mounted users flow
- revoke/resend/role updates keep last-owner protections in place

## Failure Modes
- missing auth/core bootstrap tables -> client identity bootstrap fails
- duplicate pending invitation -> `409 invite_already_pending`
- inviting an already linked member -> `409 already_member`
- invalid or non-pending invitation actions -> `404/409`
- removing or disabling the last owner -> `409`

## VERIFIED
- pytest:
  - `platform/auth-host/app/tests/test_signup_flow.py`
  - `platform/auth-host/app/tests/test_auth_me.py`
  - `platform/processing-core/app/tests/test_client_users_list.py`
  - `platform/processing-core/app/tests/test_client_users_invite.py`
  - `platform/processing-core/app/tests/test_client_users_roles.py`
  - `platform/processing-core/app/tests/test_client_invitations.py`
  - `platform/processing-core/app/tests/test_client_invitations_resend_revoke.py`
  - `platform/processing-core/app/tests/test_client_controls_wave2a.py`
- smoke cmd:
  - `scripts/smoke_client_users_roles.cmd`
- PASS:
  - unique client identity registers successfully
  - login/verify/me stay green
  - `portal/me` resolves the new client context
  - `/api/core/client/users` exposes the owner membership
  - owner role update persists and is reflected by the users list
  - invite -> list -> resend -> revoke flows succeed
  - auth/core invitation and role rows persist in storage

# CLIENT 01 - Registration -> Legal -> Contract -> Activation

## Goal
Register a client owner, accept legal terms, progress through onboarding actions, and reach an active client state through the CRM control plane.

## Actors & Roles
- Client Owner
- Admin (CRM/Ops)

## Prerequisites
- `auth-host` available.
- `processing-core` available.
- `postgres` available.
- Legal documents seeded when running locally.

## UI Flow
**Client portal**
1. Sign up / login.
2. Accept required legal documents.
3. Review onboarding status.
4. Reach activated dashboard state.

**Admin CRM**
1. Create lead.
2. Qualify lead into a client.
3. Apply onboarding actions until `FIRST_OPERATION_ALLOWED`.

## API Flow
1. **Auth**
   - `POST /v1/auth/register`
   - `POST /v1/auth/login`
   - `GET /v1/auth/me`
2. **Legal gate**
   - `GET /api/legal/required`
   - `POST /api/legal/accept`
3. **Client self-service onboarding**
   - `GET /api/v1/client/onboarding`
   - `POST /api/v1/client/onboarding/actions/REQUEST_LEGAL`
   - `POST /api/v1/client/onboarding/actions/SIGN_CONTRACT`
4. **Admin CRM onboarding**
   - `POST /api/v1/admin/crm/leads`
   - `POST /api/v1/admin/crm/leads/{lead_id}/qualify`
   - `POST /api/v1/admin/crm/clients/{client_id}/contracts`
   - `POST /api/v1/admin/crm/clients/{client_id}/onboarding/actions/ASSIGN_SUBSCRIPTION`
   - `POST /api/v1/admin/crm/clients/{client_id}/onboarding/actions/APPLY_LIMITS_PROFILE`
   - `POST /api/v1/admin/crm/clients/{client_id}/onboarding/actions/ACTIVATE_CLIENT`
   - `POST /api/v1/admin/crm/clients/{client_id}/onboarding/actions/ALLOW_FIRST_OPERATION`

## DB Touchpoints
- `users`, `user_roles`
- `legal_documents`, `legal_acceptances`
- `crm_leads`, `crm_clients`, `crm_client_profiles`, `crm_contracts`, `crm_subscriptions`
- `client_onboarding_state`, `client_onboarding_events`

## Events & Audit
- `LEGAL_ACCEPTED`
- `ONBOARDING_ACTION_APPLIED`
- `ONBOARDING_STATE_CHANGED`
- `ONBOARDING_BLOCKED`

Standalone event codes such as `CONTRACT_SIGNED`, `SUBSCRIPTION_ASSIGNED`, `LIMITS_APPLIED`, `CLIENT_ACTIVATED`, and `FIRST_OPERATION_ALLOWED` are still represented through onboarding audit/state transitions rather than separate dedicated event rows.

## Security / Gates
- Legal gate remains enforced on protected routes when enabled.
- Admin CRM routes require `admin:contracts:*`.
- Admin CRM routes require `X-CRM-Version`.

## Failure Modes
- Missing legal acceptance -> `legal_not_accepted`
- Missing contract signed -> `contract_not_signed`
- Missing subscription / limits -> `activation_prerequisites_missing`
- Missing CRM version header -> `crm_control_plane_frozen`
- Unauthorized CRM access -> `403`

## Verified
- pytest:
  - `platform/processing-core/app/tests/test_crm_onboarding.py`
  - `platform/processing-core/app/tests/test_legal_gate.py`
  - `platform/processing-core/app/tests/test_crm_admin_routes.py`
  - `platform/processing-core/app/tests/test_crm_storage_truth.py`
- smoke:
  - `scripts/smoke_onboarding_e2e.cmd`

PASS:
- admin token plus `X-CRM-Version: 1` open the CRM control-plane path
- lead create / qualify succeed
- onboarding reaches `FIRST_OPERATION_ALLOWED`
- legal gate is cleared

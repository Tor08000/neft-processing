# CLIENT 01 — Registration → Legal → Contract → Activation

## Goal
Register a client owner, accept legal terms, progress through contract/onboarding actions, and activate the client through CRM controls.

## Actors & Roles
- Client Owner (primary client user)
- Admin (CRM/Ops)

## Prerequisites
- Auth-host available (`platform/auth-host`).
- Processing-core API available (`platform/processing-core`).
- Legal documents seeded (`scripts/seed_legal.py` if running locally).

## UI Flow
**Client portal**
1. Sign up / login.
2. Legal acceptance page (required docs).
3. Onboarding status page (REQUEST_LEGAL / SIGN_CONTRACT actions).
4. Activation status → dashboard.

**Admin (CRM)**
1. Lead → qualify → client profile.
2. Assign subscription, apply limits profile, activate client, allow first operation.

## API Flow
1. **Auth**
   - `POST /v1/auth/register` (auth-host) — register user.
   - `POST /v1/auth/login` — obtain token.
   - `GET /v1/auth/me` — confirm identity.
2. **Legal gate**
   - `GET /api/legal/required` — list required legal documents.
   - `POST /api/legal/accept` — accept each required doc.
3. **Client onboarding (self-service)**
   - `GET /api/v1/client/onboarding` — onboarding status.
   - `POST /api/v1/client/onboarding/actions/REQUEST_LEGAL` — request legal (records intent).
   - `POST /api/v1/client/onboarding/actions/SIGN_CONTRACT` — mark contract signed (no document generation).
4. **CRM onboarding (admin)**
   - `POST /api/crm/leads/{lead_id}/qualify` — convert lead to client.
   - `POST /api/crm/clients/{client_id}/contracts` — create CRM contract (no doc/version workflow).
   - `POST /api/crm/clients/{client_id}/onboarding/actions/ASSIGN_SUBSCRIPTION`.
   - `POST /api/crm/clients/{client_id}/onboarding/actions/APPLY_LIMITS_PROFILE`.
   - `POST /api/crm/clients/{client_id}/onboarding/actions/ACTIVATE_CLIENT`.
   - `POST /api/crm/clients/{client_id}/onboarding/actions/ALLOW_FIRST_OPERATION`.

**NOT IMPLEMENTED**
- Contract draft/version/issue/sign endpoints (`/contracts/{id}/versions`, `/contracts/{id}/issue`, `/contracts/{id}/sign`).

## DB Touchpoints
- `auth-host`: `users`, `user_roles`.
- Legal: `legal_documents`, `legal_acceptances`.
- CRM: `crm_leads`, `crm_clients`, `crm_client_profiles`, `crm_contracts`, `crm_subscriptions`.
- Onboarding: `client_onboarding_state`, `client_onboarding_events`.

## Events & Audit
- `LEGAL_ACCEPTED` — audit event emitted on document acceptance (legal service).
- `ONBOARDING_ACTION_APPLIED`, `ONBOARDING_STATE_CHANGED`, `ONBOARDING_BLOCKED` — CRM onboarding audit events.
- `CRM_CONTRACT_ACTIVATED`, `CRM_CONTRACT_VERSION_BUMPED` — CRM contract status changes.

**NOT IMPLEMENTED (explicit event codes in requirement)**
- `CONTRACT_ISSUED`, `CONTRACT_SIGNED`, `SUBSCRIPTION_ASSIGNED`, `LIMITS_APPLIED`, `CLIENT_ACTIVATED`, `FIRST_OPERATION_ALLOWED` are not emitted as standalone event codes; current implementation records onboarding audit events instead.

## Security / Gates
- Legal gate enforced on protected routes when `LEGAL_GATE_ENABLED=true`.
- Admin CRM routes require `admin:contracts:*` permission and `X-CRM-Version` header.

## Failure modes
- Missing legal acceptance → onboarding blocked (`legal_not_accepted`).
- Missing contract signed → onboarding blocked (`contract_not_signed`).
- Missing subscription/limits → activation blocked (`activation_prerequisites_missing`).
- Unauthorized access to CRM routes → `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_crm_onboarding.py`, `platform/processing-core/app/tests/test_legal_gate.py`.
- smoke cmd: `scripts/smoke_onboarding_e2e.cmd`.
- PASS: onboarding reaches `FIRST_OPERATION_ALLOWED` and legal gate is cleared.

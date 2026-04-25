# PARTNER 09 - Partner Onboarding

## Goal
An authenticated partner completes internal onboarding and becomes `ACTIVE` without fake portal fallbacks.

## Actors & Roles
- Partner owner or manager
- Admin legal operator

## Prerequisites
- Seeded partner account `partner@neft.local`
- Seeded admin account `admin@neft.local`
- Core onboarding enabled
- Canonical partner onboarding owner mounted under `/api/core/partner/onboarding/*`

## UI Flow
**Partner portal**
- Login
- `portal/me` resolves `NEEDS_ONBOARDING` with `partner_onboarding`
- shell redirects `/` to `/onboarding`
- partner completes:
  - profile step
  - legal profile/details step
  - legal acceptance step
- admin verifies legal profile
- partner activates and reaches the normal workspace

## API Flow
**Partner**
- `GET /api/core/partner/auth/verify`
- `GET /api/core/portal/me`
- `GET /api/core/partner/onboarding`
- `PATCH /api/core/partner/onboarding/profile`
- `PUT /api/core/partner/legal/profile`
- `PUT /api/core/partner/legal/details`
- `GET /api/core/legal/required`
- `POST /api/core/legal/accept`
- `POST /api/core/partner/onboarding/activate`

**Admin**
- `GET /api/core/admin/auth/verify`
- `POST /api/core/v1/admin/legal/partners/{partner_id}/status`

## DB Touchpoints
- `partners`
- `partner_user_roles`
- `partner_legal_profiles`
- `partner_legal_details`
- `legal_documents`
- `legal_acceptances`
- `audit_log`

No separate onboarding table is required in this contour. Onboarding truth is derived from canonical partner status, legal state, and accepted legal documents.

## Events & Audit
- `PARTNER_ONBOARDING_STARTED`
- `PARTNER_ONBOARDING_PROFILE_UPDATED`
- `PARTNER_ACTIVATED`
- partner legal review status persists through `partner_legal_status_changed`

## Security / Gates
- Authenticated partner-only flow; this is not anonymous signup
- activation remains blocked until:
  - brand + contacts are present
  - required legal documents are accepted
  - legal profile/details are complete
  - admin legal verification reaches `VERIFIED`

## Failure modes
- Partner not linked -> `partner_not_linked`
- Incomplete checklist -> `409 partner_onboarding_incomplete`
- Missing legal verification keeps activation blocked with `legal_review_pending`
- Absent mounted owner routes must fail explicitly, not fall back to demo/profile shortcuts

## VERIFIED
- pytest:
  - `platform/processing-core/app/tests/test_partner_onboarding_api.py`
- frontend vitest:
  - `frontends/partner-portal/src/pages/PartnerOnboardingPage.test.tsx`
  - `frontends/partner-portal/src/AppShell.test.tsx`
- smoke cmd:
  - `scripts/smoke_partner_onboarding.cmd`
- PASS:
  - partner shell redirects into mounted onboarding owner route
  - activation is blocked before admin legal verification
  - admin legal verification unblocks activation
  - final `portal/me` state becomes `ACTIVE`
  - partner/legal/audit rows persist expected final truth

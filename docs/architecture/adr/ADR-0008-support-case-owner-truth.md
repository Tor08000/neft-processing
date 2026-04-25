# ADR-0008 — Support / Cases Owner Truth

## Status

Accepted

## Decision

- Canonical operational owner for support, incidents, order issues, and dispute-adjacent case intake is `processing-core` `cases` under `/api/core/cases*`.
- `support_requests` no longer owns product state or storage. `/api/v1/support/requests*` remains a compatibility API tail that materializes or reads canonical `cases`.
- `support_tickets` remains a helpdesk/SLA/comments/attachments sidecar for client support UX, but it must be linked to the same canonical `case` by id/source-ref and may not diverge as a parallel owner.
- Marketplace order issues, billing dunning disputes, logistics incidents, and document evidence flows must converge into canonical `cases`.

## Unified model

Canonical `Case` truth:

- `id`
- `kind`: `support | order | dispute | incident` for this contour
- `entity_type`
- `entity_id`
- `status`
- `priority`
- `queue`
- `client_id`
- `partner_id`
- `created_by`
- `assigned_to`
- `timeline`
- `comments`
- `case_source_ref_type`
- `case_source_ref_id`

`support_requests` and `support_tickets` may project into that model, but they are no longer separate product owners.

## Lifecycle truth

- Canonical lifecycle is:
  - `TRIAGE`
  - `IN_PROGRESS`
  - `WAITING`
  - `RESOLVED`
  - `CLOSED`
- Compatibility mapping for `support_requests` keeps:
  - `OPEN -> TRIAGE`
  - `WAITING -> WAITING`
  - `RESOLVED -> RESOLVED`
  - `CLOSED -> CLOSED`
- No route/UI should invent a second lifecycle for support.

## Owner map

### Canonical owner
- `platform/processing-core/app/routers/cases.py`
- `platform/processing-core/app/services/cases_service.py`
- `platform/processing-core/app/services/support_cases.py`

### Compatibility / sidecar surfaces
- `platform/processing-core/app/api/v1/endpoints/support_requests.py`
  - compatibility-only adapter over canonical `cases`
- `platform/processing-core/app/models/support_ticket.py`
  - helpdesk/SLA/comments/attachments sidecar
- `frontends/partner-portal/src/pages/SupportRequests*`
  - compatibility UI paths backed by canonical `cases`
- `frontends/client-portal/src/pages/SupportTickets*`
  - ticket/helpdesk UX that must expose linked canonical case

### Integrated producers
- marketplace order issue creation
- billing dunning dispute/support creation
- helpdesk inbound comment/status sync

## Explicit compatibility state

- `/api/v1/support/requests*`
  - final compatibility tail
  - no new owner-only semantics
  - no new storage divergence
- partner UI route `/support/requests*`
  - compatibility UX path
  - allowed while backed by canonical `cases`
- client support tickets
  - not removable
  - must stay case-linked and not operate as an unlinked parallel state machine

## What this ADR does not approve

- changing refund/dispute money semantics
- changing auth/RBAC semantics
- removing public gateway families without separate route verification
- destructive removal of support tables

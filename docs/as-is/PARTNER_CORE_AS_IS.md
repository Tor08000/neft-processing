# Partner Core — AS-IS (Sprint B)

## Scope (P0)

- Partner profile (`partner_profiles`) with status ONBOARDING/ACTIVE/SUSPENDED.
- Partner offers (`partner_offers`) for catalog management.
- Partner inbound orders (`partner_orders`) with SLA timers.
- Partner analytics summary (orders + SLA breaches).
- In-app notifications for partner events.
- Audit events for partner order actions + SLA breaches.
- Partner/client separation guard (partner tokens cannot access client endpoints).

## Data Model

### partner_profiles

- `org_id` (unique)
- `status`: ONBOARDING | ACTIVE | SUSPENDED
- `display_name`
- `contacts_json`
- `meta_json`
- timestamps

### partner_offers

- `org_id`
- `code` (unique per org)
- `title`, `description`
- `base_price`, `currency`
- `status`: ACTIVE | INACTIVE
- timestamps

### partner_orders

- `partner_org_id`
- `client_org_id` (optional)
- `offer_id` (optional)
- `title`
- `status`: NEW | ACCEPTED | REJECTED | IN_PROGRESS | DONE
- SLA: `response_due_at`, `resolution_due_at`
- timestamps

## API Endpoints (core prefix)

### `/api/core/portal/me`

- Includes `partner.profile` and `partner.status` when org has PARTNER role.
- Capabilities include `PARTNER_CORE`, `PARTNER_CATALOG`, `PARTNER_ORDERS`, `PARTNER_ANALYTICS`.

### Partner profile

- `GET /api/core/partner/profile`
- `PATCH /api/core/partner/profile` (updates `display_name`, `contacts_json`; promotes status to ACTIVE if ONBOARDING)

### Partner offers

- `GET /api/core/partner/offers`
- `POST /api/core/partner/offers`
- `PATCH /api/core/partner/offers/{offer_id}`
- `POST /api/core/partner/offers/{offer_id}/activate`
- `POST /api/core/partner/offers/{offer_id}/deactivate`

### Partner orders

- `GET /api/core/partner/orders` (cursor pagination via `cursor`, `limit`)
- `GET /api/core/partner/orders/{order_id}`
- `POST /api/core/partner/orders/{order_id}/accept`
- `POST /api/core/partner/orders/{order_id}/reject`
- `POST /api/core/partner/orders/{order_id}/status`
- `POST /api/core/partner/orders/seed` (admin helper)

### Partner analytics

- `GET /api/core/partner/analytics/summary?from&to`

## RBAC / Capabilities

- `partner:profile:view`, `partner:profile:manage`
- `partner:offers:list`, `partner:offers:manage`
- `partner:orders:list`, `partner:orders:view`, `partner:orders:update`
- `partner:analytics:view`

Endpoints also check capabilities:

- Profile → `PARTNER_CORE`
- Offers → `PARTNER_CATALOG`
- Orders → `PARTNER_ORDERS`
- Analytics → `PARTNER_ANALYTICS`

## Audit Events

- `partner_order_accepted`
- `partner_order_rejected`
- `partner_order_status_changed`
- `partner_sla_breached`
- `partner_client_forbidden` (partner attempted client endpoint)

## Notifications

- `partner_new_order`
- `partner_order_status_changed`

## How to verify

1. Add `PARTNER` role to org (admin endpoint).
2. Call `GET /api/core/portal/me` and check `partner.profile/status`.
3. Create offer via `POST /api/core/partner/offers` and verify listing.
4. Seed order via `POST /api/core/partner/orders/seed`.
5. Accept / reject / status update order and confirm audit events.
6. Call `GET /api/core/partner/analytics/summary` and verify counts.

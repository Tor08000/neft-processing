# Partner Portal expected endpoints (from frontend)

Source: `frontends/partner-portal/src/api/*.ts` client modules. Base URLs are built from:

- Core API base: `/api/core` (via `CORE_API_BASE` / `CORE_ROOT_API_BASE`).
- Auth API base: `/api/auth`.

## Auth API (`/api/auth`)

| Method | Path |
| --- | --- |
| POST | `/api/auth/v1/auth/login` |
| GET | `/api/auth/v1/auth/me` |

## Core API (`/api/core`)

### Portal / session

| Method | Path |
| --- | --- |
| GET | `/api/core/portal/me` |

### Partner shell bootstrap / workspace routing

| Method | Path |
| --- | --- |
| GET | `/api/core/portal/me` |

`/api/core/portal/me.partner.kind`, `.partner_roles`, `.workspaces`, and `.default_route` are the canonical inputs for partner shell composition.

### Finance workspace (`FINANCE_PARTNER` or finance-capable partner)

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/finance/dashboard` |
| GET | `/api/core/partner/balance` |
| GET | `/api/core/partner/ledger` |
| GET | `/api/core/partner/ledger/{entryId}/explain` |
| GET | `/api/core/partner/payouts` |
| GET | `/api/core/partner/payouts/preview` |
| POST | `/api/core/partner/payouts/request` |
| GET | `/api/core/partner/invoices` |
| GET | `/api/core/partner/acts` |
| POST | `/api/core/partner/exports/jobs` |

Mounted partner finance shell calls this core-prefixed family only. Public `/api/partner/acts|balance|invoices|ledger*|payouts*` routes remain parity-adjacent compatibility surfaces for other repo-visible consumers/tests and must not be treated as the shell owner.

Removed from the mounted partner shell in this contour:

- `/api/core/partner/stations*`
- `/api/core/partner/transactions*`
- `/api/core/partner/payout-batches*`
- `/api/core/partner/settings`
- generic `/api/core/partner/documents*`
- `/api/core/partner/refunds*`
- `/api/core/partner/prices*`
- `/api/core/partner/contracts`
- `/api/core/partner/settlements*`

Frozen finance shell gap in the default topology:

- `/api/core/partner/contracts` and `/api/core/partner/settlements*` are not mounted by the default backend app.
- Partner shell keeps `/contracts` and `/settlements*` only as honest frozen frontend pages so old links do not silently break.

### Marketplace workspace (`MARKETPLACE_PARTNER`)

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/products` |
| GET | `/api/core/partner/products/{productId}` |
| POST | `/api/core/partner/products` |
| PATCH | `/api/core/partner/products/{productId}` |
| POST | `/api/core/partner/products/{productId}/publish` |
| POST | `/api/core/partner/products/{productId}/archive` |
| GET | `/api/core/partner/offers` |
| POST | `/api/core/partner/offers` |
| PUT | `/api/core/partner/offers/{offerId}` |
| POST | `/api/core/partner/offers/{offerId}/activate` |
| POST | `/api/core/partner/offers/{offerId}/disable` |
| GET | `/api/core/v1/marketplace/partner/orders` |
| GET | `/api/core/v1/marketplace/partner/orders/{orderId}` |
| GET | `/api/core/v1/marketplace/partner/orders/{orderId}/events` |
| GET | `/api/core/v1/marketplace/partner/orders/{orderId}/documents` |
| GET | `/api/core/v1/marketplace/partner/orders/{orderId}/settlement` |
| GET | `/api/core/v1/marketplace/partner/orders/{orderId}/sla` |
| POST | `/api/core/v1/marketplace/partner/orders/{orderId}:confirm` |
| POST | `/api/core/v1/marketplace/partner/orders/{orderId}:decline` |
| POST | `/api/core/v1/marketplace/partner/orders/{orderId}/proofs` |
| POST | `/api/core/v1/marketplace/partner/orders/{orderId}:complete` |

### Services workspace (`SERVICE_PARTNER`)

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/catalog` |
| GET | `/api/core/partner/catalog/{catalogId}` |
| POST | `/api/core/partner/catalog` |
| PUT | `/api/core/partner/catalog/{catalogId}` |
| POST | `/api/core/partner/catalog/{catalogId}/activate` |
| POST | `/api/core/partner/catalog/{catalogId}/disable` |
| POST | `/api/core/partner/catalog/import?mode=preview&import_mode={importMode}` |
| POST | `/api/core/partner/catalog/import?mode=apply&import_mode={importMode}` |

### Partner legal / profile workspace

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/legal/profile` |
| PUT | `/api/core/partner/legal/profile` |
| PUT | `/api/core/partner/legal/details` |
| GET | `/api/core/partner/self-profile` |
| PATCH | `/api/core/partner/self-profile` |
| GET | `/api/core/partner/locations` |
| POST | `/api/core/partner/locations` |
| PATCH | `/api/core/partner/locations/{locationId}` |
| DELETE | `/api/core/partner/locations/{locationId}` |
| GET | `/api/core/partner/users` |
| POST | `/api/core/partner/users` |
| DELETE | `/api/core/partner/users/{userId}` |
| GET | `/api/core/partner/terms` |

Current write truth in this workspace:

- `/api/core/partner/self-profile` is writable for `OWNER`, `MANAGER`, `FINANCE_MANAGER`
- `/api/core/partner/locations*` is writable for `OWNER`, `MANAGER`
- `/api/core/partner/users*` is writable for `OWNER` only
- `/api/core/partner/terms` is read-only

### Legal gate

| Method | Path |
| --- | --- |
| GET | `/api/core/legal/required` |
| GET | `/api/core/legal/documents/{code}` |
| POST | `/api/core/legal/accept` |

### Support / cases

| Method | Path |
| --- | --- |
| POST | `/api/core/cases` |
| GET | `/api/core/cases` |
| GET | `/api/core/cases/{caseId}` |

Partner UX compatibility entrypoint remains `/support/requests*`, but it is backed by canonical cases rather than a separate support owner.
Mounted partner shell also accepts `/cases` and `/cases/{caseId}` as canonical case-trail aliases inside the same support workspace, so list/detail CTAs can resolve straight into the shared lifecycle without introducing a second backend owner.

## Frozen compatibility tails outside the mounted shell

These routes still exist or are still tracked as compatibility tails and were not removed in this wave:

- `/api/core/partner/me`
- `/api/partner/dashboard`
- `/api/partner/acts`, `/api/partner/balance`, `/api/partner/invoices`, `/api/partner/ledger*`, `/api/partner/payouts*`
- `/api/v1/partner/fuel/stations/{stationId}/prices`
- `/api/v1/partner/fuel/stations/{stationId}/prices/import`

### Webhooks (partner-owned, integration-hub self-service)

Canonical external family for partner webhook self-service: `/api/int/v1/webhooks/*`.

Separate contour: processing-core helpdesk inbound webhooks under `/api/core/webhooks/helpdesk/*`.

| Method | Path |
| --- | --- |
| GET | `/api/int/v1/webhooks/endpoints?owner_type=PARTNER&owner_id={ownerId}` |
| POST | `/api/int/v1/webhooks/endpoints` |
| PATCH | `/api/int/v1/webhooks/endpoints/{endpointId}` |
| POST | `/api/int/v1/webhooks/endpoints/{endpointId}/rotate-secret` |
| POST | `/api/int/v1/webhooks/endpoints/{endpointId}/test` |
| POST | `/api/int/v1/webhooks/endpoints/{endpointId}/pause` |
| POST | `/api/int/v1/webhooks/endpoints/{endpointId}/resume` |
| POST | `/api/int/v1/webhooks/endpoints/{endpointId}/replay` |
| GET | `/api/int/v1/webhooks/endpoints/{endpointId}/sla?window={window}` |
| GET | `/api/int/v1/webhooks/endpoints/{endpointId}/alerts` |
| GET | `/api/int/v1/webhooks/subscriptions?endpoint_id={endpointId}` |
| POST | `/api/int/v1/webhooks/subscriptions` |
| PATCH | `/api/int/v1/webhooks/subscriptions/{subscriptionId}` |
| DELETE | `/api/int/v1/webhooks/subscriptions/{subscriptionId}` |
| GET | `/api/int/v1/webhooks/deliveries?endpoint_id={endpointId}` |
| GET | `/api/int/v1/webhooks/deliveries/{deliveryId}` |
| POST | `/api/int/v1/webhooks/deliveries/{deliveryId}/retry` |

`/api/int/v1/webhooks/event-types` is not part of the current Integrations page runtime flow and is not treated as a required canonical route here.

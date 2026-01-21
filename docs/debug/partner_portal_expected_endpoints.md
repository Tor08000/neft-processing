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

### Partner portal summaries

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/dashboard` |
| GET | `/api/core/partner/contracts` |
| GET | `/api/core/partner/settlements` |
| GET | `/api/core/partner/settlements/{settlementRef}` |
| POST | `/api/core/partner/settlements/{settlementRef}/confirm` |

### Partner core data

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/profile` |
| GET | `/api/core/partner/stations` |
| GET | `/api/core/partner/stations/{stationId}` |
| GET | `/api/core/partner/transactions` |
| GET | `/api/core/partner/transactions/{transactionId}` |
| GET | `/api/core/partner/settlements` |
| GET | `/api/core/partner/settlements/{settlementId}` |
| POST | `/api/core/partner/settlements/{settlementId}/confirm` |
| POST | `/api/core/partner/settlements/{settlementId}/reconciliation-requests` |
| GET | `/api/core/partner/payout-batches` |
| GET | `/api/core/partner/documents` |
| GET | `/api/core/partner/documents/{documentId}` |
| GET | `/api/core/partner/services` |
| GET | `/api/core/partner/settings` |

### Partner legal

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/legal/profile` |
| PUT | `/api/core/partner/legal/profile` |
| PUT | `/api/core/partner/legal/details` |

### Partner finance

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/balance` |
| GET | `/api/core/partner/ledger` |
| GET | `/api/core/partner/ledger/{entryId}/explain` |
| POST | `/api/core/partner/payouts/request` |
| GET | `/api/core/partner/payouts` |
| GET | `/api/core/partner/payouts/preview` |
| GET | `/api/core/partner/payouts/{payoutId}/trace` |
| GET | `/api/core/partner/invoices` |
| GET | `/api/core/partner/acts` |
| POST | `/api/core/partner/exports/jobs` |
| GET | `/api/core/partner/exports/jobs?limit={limit}` |

### Marketplace catalog / products

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/profile` |
| POST | `/api/core/partner/profile` |
| GET | `/api/core/partner/products` |
| GET | `/api/core/partner/products/{productId}` |
| POST | `/api/core/partner/products` |
| PATCH | `/api/core/partner/products/{productId}` |
| POST | `/api/core/partner/products/{productId}/publish` |
| POST | `/api/core/partner/products/{productId}/archive` |

### Marketplace catalog items

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

### Marketplace offers

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/offers` |
| POST | `/api/core/partner/offers` |
| PUT | `/api/core/partner/offers/{offerId}` |
| POST | `/api/core/partner/offers/{offerId}/activate` |
| POST | `/api/core/partner/offers/{offerId}/disable` |

### Marketplace orders & documents

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/orders` |
| GET | `/api/core/partner/orders/{orderId}` |
| GET | `/api/core/partner/orders/{orderId}/events` |
| GET | `/api/core/partner/orders/{orderId}/documents` |
| GET | `/api/core/partner/orders/{orderId}/settlement` |
| GET | `/api/core/partner/orders/{orderId}/sla` |
| POST | `/api/core/partner/orders/{orderId}/accept` |
| POST | `/api/core/partner/orders/{orderId}/start` |
| POST | `/api/core/partner/orders/{orderId}/reject` |
| POST | `/api/core/partner/orders/{orderId}/progress` |
| POST | `/api/core/partner/orders/{orderId}/complete` |
| POST | `/api/core/partner/orders/{orderId}/fail` |
| GET | `/api/core/partner/settlements?source=MARKETPLACE&order_id={orderId}` |
| GET | `/api/core/partner/documents/{documentId}` |
| POST | `/api/core/partner/documents/{documentId}/sign/request` |
| POST | `/api/core/partner/documents/{documentId}/edo/dispatch` |
| GET | `/api/core/partner/documents/{documentId}/edo/events` |

### Marketplace refunds

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/refunds` |
| GET | `/api/core/partner/refunds/{refundId}` |
| POST | `/api/core/partner/refunds/{refundId}/approve` |
| POST | `/api/core/partner/refunds/{refundId}/deny` |

### Partner pricing

| Method | Path |
| --- | --- |
| GET | `/api/core/partner/prices/versions` |
| POST | `/api/core/partner/prices/versions` |
| GET | `/api/core/partner/prices/versions/{versionId}` |
| POST | `/api/core/partner/prices/versions/{versionId}/validate` |
| POST | `/api/core/partner/prices/versions/{versionId}/publish` |
| POST | `/api/core/partner/prices/versions/{versionId}/rollback` |
| POST | `/api/core/partner/prices/versions/{versionId}/import` |
| GET | `/api/core/partner/prices/versions/{versionId}/items` |
| GET | `/api/core/partner/prices/versions/{versionId}/diff?to_version_id={toVersionId}` |
| GET | `/api/core/partner/prices/versions/{versionId}/audit` |
| GET | `/api/core/partner/prices/analytics/versions` |
| GET | `/api/core/partner/prices/analytics/versions/series` |
| GET | `/api/core/partner/prices/analytics/offers` |
| GET | `/api/core/partner/prices/analytics/insights` |

### Legal gate

| Method | Path |
| --- | --- |
| GET | `/api/core/legal/required` |
| GET | `/api/core/legal/documents/{code}` |
| POST | `/api/core/legal/accept` |

### Support requests

| Method | Path |
| --- | --- |
| POST | `/api/core/support/requests` |
| GET | `/api/core/support/requests` |
| GET | `/api/core/support/requests/{requestId}` |

### Webhooks (partner-owned)

| Method | Path |
| --- | --- |
| GET | `/api/core/v1/webhooks/endpoints?owner_type=PARTNER&owner_id={ownerId}` |
| GET | `/api/core/v1/webhooks/event-types?owner_type=PARTNER` |
| POST | `/api/core/v1/webhooks/endpoints` |
| PATCH | `/api/core/v1/webhooks/endpoints/{endpointId}` |
| POST | `/api/core/v1/webhooks/endpoints/{endpointId}/rotate-secret` |
| POST | `/api/core/v1/webhooks/endpoints/{endpointId}/test` |
| POST | `/api/core/v1/webhooks/endpoints/{endpointId}/pause` |
| POST | `/api/core/v1/webhooks/endpoints/{endpointId}/resume` |
| POST | `/api/core/v1/webhooks/endpoints/{endpointId}/replay` |
| GET | `/api/core/v1/webhooks/endpoints/{endpointId}/sla?window={window}` |
| GET | `/api/core/v1/webhooks/endpoints/{endpointId}/alerts` |
| GET | `/api/core/v1/webhooks/subscriptions?endpoint_id={endpointId}` |
| POST | `/api/core/v1/webhooks/subscriptions` |
| PATCH | `/api/core/v1/webhooks/subscriptions/{subscriptionId}` |
| DELETE | `/api/core/v1/webhooks/subscriptions/{subscriptionId}` |
| GET | `/api/core/v1/webhooks/deliveries?endpoint_id={endpointId}` |
| GET | `/api/core/v1/webhooks/deliveries/{deliveryId}` |
| POST | `/api/core/v1/webhooks/deliveries/{deliveryId}/retry` |

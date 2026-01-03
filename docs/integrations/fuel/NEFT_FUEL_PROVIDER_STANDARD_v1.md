# NEFT Fuel Provider Standard v1

**Status:** ACTIVE (v1)

This document is the **source-of-truth contract** for integrating a fuel provider into NEFT. It is aligned with the current provider interface in:

- `platform/processing-core/app/integrations/fuel/base.py`
- `platform/processing-core/app/integrations/fuel/normalize.py`
- `platform/processing-core/app/services/fleet_ingestion_service.py`
- `platform/processing-core/app/integrations/fuel/jobs.py`
- `platform/processing-core/app/integrations/fuel/models.py`

If a capability is **not implemented** in the codebase, it is explicitly marked as **NOT IMPLEMENTED** here.

---

## A1. Overview

### What is a “Fuel Provider” in NEFT?

A **Fuel Provider** is an integration adapter that pulls transactions and (optionally) statements from an external partner and maps them into NEFT’s canonical fuel transaction schema. In NEFT, a provider is a Python class implementing the `FuelProviderConnector` protocol.

### Architecture placement

```
Provider → Ingestion (poll/backfill/replay) → Normalize → Dedup → Append-only txn → Policies/Anomaly → Notifications
```

- **Provider**: external partner API / EDI feed.
- **Ingestion**: NEFT polling, backfill, replay, and EDI parsing in `app/integrations/fuel/jobs.py`.
- **Normalize**: provider → canonical mapping in `app/integrations/fuel/normalize.py`.
- **Dedup**: NEFT’s dedupe rules in `app/services/fleet_ingestion_service.py`.
- **Append-only txn**: stored in `FuelTransaction` (see `app/models/fuel.py`).
- **Policies/Anomaly/Notifications**: executed after ingest.

### Definitions

| Term | Definition | Source |
| --- | --- | --- |
| station | Fuel station identifier used in transactions (`station_id`), mapped to internal station via `station_external_id`. | `app/services/fleet_ingestion_service.py` |
| product | Fuel product type (NOT IMPLEMENTED in provider interface v1). | — |
| price | Price for product (NOT IMPLEMENTED in provider interface v1). | — |
| transaction | A fuel purchase or related charge ingested via `fetch_transactions`. | `app/integrations/fuel/base.py` |
| statement | Provider statement (period summary) returned by `fetch_statements`. | `app/integrations/fuel/base.py` |
| external_id | Provider’s own unique identifier for a transaction or statement (`provider_tx_id`, `provider_statement_id`). | `app/integrations/fuel/base.py` |

---

## A2. Provider Interface (source-of-truth = code)

**Interface:** `FuelProviderConnector` in `platform/processing-core/app/integrations/fuel/base.py`.

### Required methods

| Method | Description | Required | Inputs | Output |
| --- | --- | --- | --- | --- |
| `health(conn)` | Provider health check. | YES | `conn` (provider connection config) | `HealthResult` |
| `list_cards(conn, cursor=None)` | List provider cards (optional in flow, required by interface). | YES | `conn`, `cursor` | `CardsPage` |
| `block_card(conn, provider_card_id, reason)` | Block card at provider. | YES | `conn`, `provider_card_id`, `reason` | `ProviderResult` |
| `unblock_card(conn, provider_card_id, reason)` | Unblock card at provider. | YES | `conn`, `provider_card_id`, `reason` | `ProviderResult` |
| `fetch_transactions(conn, since, until, cursor=None)` | Pull transactions in a time window. | YES | `conn`, `since`, `until`, `cursor` | `TxPage` |
| `fetch_statements(conn, period_start, period_end)` | Fetch statement (period summary). | YES | `conn`, `period_start`, `period_end` | `ProviderStatement` |
| `map_transaction(item)` | Map provider transaction to canonical transaction. | YES | `ProviderTransaction` | `dict` (CanonicalTransaction fields) |
| `map_statement(statement)` | Map provider statement to canonical statement. | YES | `ProviderStatement` | `dict` (CanonicalStatement fields) |
| `map_raw_event(payload)` | Map redacted raw payload to canonical transaction for replay. | YES | `dict` | `dict` (CanonicalTransaction fields) |

### Data objects

#### `HealthResult`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | `str` | YES | `"ok"`, `"degraded"`, or provider-specific status. |
| `details` | `dict[str, str] \| None` | NO | Optional diagnostics. |

#### `ProviderResult`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | `bool` | YES | Whether action succeeded. |
| `message` | `str \| None` | NO | Provider message or error reason. |

#### `ProviderCard`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `provider_card_id` | `str` | YES | Provider-side card identifier. |
| `status` | `str` | YES | Provider card status. |
| `card_alias` | `str \| None` | NO | Alias used to match NEFT card (see mapping). |
| `meta` | `dict \| None` | NO | Extra provider metadata. |

#### `ProviderTransaction`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `provider_tx_id` | `str \| None` | RECOMMENDED | Provider transaction ID; used for dedupe. |
| `provider_card_id` | `str \| None` | RECOMMENDED | Provider card ID for mapping. |
| `occurred_at` | `datetime` | YES | Event timestamp. |
| `amount` | `Decimal` | YES | Total amount. |
| `currency` | `str` | YES | ISO currency (e.g., `RUB`). |
| `volume_liters` | `Decimal \| None` | NO | Fuel volume in liters. |
| `category` | `str \| None` | NO | Category (see `normalize.py`, e.g., `FUEL`). |
| `merchant_name` | `str \| None` | NO | Merchant/station display name. |
| `station_id` | `str \| None` | NO | External station identifier. |
| `location` | `str \| None` | NO | Location free text or coordinates. |
| `raw_payload` | `dict \| None` | NO | Full raw payload for audit/replay. |

#### `ProviderStatement`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `provider_statement_id` | `str \| None` | RECOMMENDED | Provider statement ID. |
| `period_start` | `datetime` | YES | Statement period start. |
| `period_end` | `datetime` | YES | Statement period end. |
| `currency` | `str` | YES | ISO currency. |
| `total_in` | `Decimal \| None` | NO | Total incoming amount. |
| `total_out` | `Decimal \| None` | NO | Total outgoing amount. |
| `closing_balance` | `Decimal \| None` | NO | Closing balance. |
| `lines` | `list[dict] \| None` | NO | Statement line items. |
| `raw_payload` | `dict \| None` | NO | Raw payload for audit. |

#### `CardsPage` / `TxPage`
Source: `app/integrations/fuel/base.py`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `items` | `list[ProviderCard]` / `list[ProviderTransaction]` | YES | Page items. |
| `next_cursor` | `str \| None` | NO | Cursor for next page. |

---

## A3. Data Contracts (Schemas)

### Station (NOT IMPLEMENTED)

- **Status:** NOT IMPLEMENTED in provider interface v1.
- **Reason:** No `fetch_stations` or `map_station` in `FuelProviderConnector`.

### Product (NOT IMPLEMENTED)

- **Status:** NOT IMPLEMENTED in provider interface v1.
- **Reason:** No `map_product` or product schema in provider base.

### Price (NOT IMPLEMENTED)

- **Status:** NOT IMPLEMENTED in provider interface v1.
- **Reason:** No `fetch_prices` in provider base.

### Transaction (ProviderTransaction → CanonicalTransaction → FleetIngestItemIn)

#### Required vs optional fields

| Field | Required | Source | Notes |
| --- | --- | --- | --- |
| `provider_tx_id` | RECOMMENDED | ProviderTransaction | Primary dedupe key when present. |
| `provider_card_id` | RECOMMENDED | ProviderTransaction | Used for card mapping. |
| `occurred_at` | YES | ProviderTransaction | Event timestamp. |
| `amount` | YES | ProviderTransaction | Decimal amount. |
| `currency` | YES | ProviderTransaction | ISO currency string. |
| `volume_liters` | NO | ProviderTransaction | Decimal liters. |
| `category` | NO | ProviderTransaction | Normalized via `normalize.py`. |
| `merchant_name` | NO | ProviderTransaction | Used to build merchant key. |
| `station_id` | NO | ProviderTransaction | External station id. |
| `location` | NO | ProviderTransaction | Location string. |
| `raw_payload` | NO | ProviderTransaction | Stored redacted for audit/replay. |

#### CanonicalTransaction fields (mapping target)
Source: `app/integrations/fuel/normalize.py`

- `provider_code` (str, REQUIRED)
- `provider_tx_id` (str | None)
- `provider_card_id` (str | None)
- `card_alias` (str | None)
- `occurred_at` (datetime, REQUIRED)
- `amount` (Decimal, REQUIRED)
- `currency` (str, REQUIRED)
- `volume_liters` (Decimal | None)
- `category` (str | None)
- `merchant_name` (str | None)
- `station_id` (str | None)
- `location` (str | None)
- `raw_payload` (dict | None)

#### FleetIngestItemIn fields (ingest payload)
Source: `app/schemas/fleet_ingestion.py`

- `provider_tx_id` (str | None)
- `client_ref` (str | None)
- `card_alias` (str | None)
- `masked_pan` (str | None)
- `occurred_at` (datetime, REQUIRED)
- `amount` (Decimal, REQUIRED)
- `currency` (str | None, default `"RUB"`)
- `volume_liters` (Decimal | None)
- `category` (str | None)
- `merchant_name` (str | None)
- `station_id` (str | None)
- `location` (str | None)
- `external_ref` (str | None) → defaults to `provider_tx_id` in `canonical_to_ingest_item`
- `raw_payload` (dict | None)

#### Example JSON (ProviderTransaction)

```json
{
  "provider_tx_id": "tx-984312",
  "provider_card_id": "card-721",
  "occurred_at": "2024-06-01T10:15:00Z",
  "amount": "1850.50",
  "currency": "RUB",
  "volume_liters": "45.1",
  "category": "FUEL",
  "merchant_name": "NEFT Station 12",
  "station_id": "station-12",
  "location": "55.7558,37.6176",
  "raw_payload": {
    "provider_status": "SETTLED",
    "pump_id": "P-3"
  }
}
```

#### Dedupe / idempotency keys

Deduplication is enforced in `app/services/fleet_ingestion_service.py`:

1. If `provider_tx_id` is present: dedupe by `(provider_code, provider_tx_id)`.
2. Else if `external_ref` is present: dedupe by `(provider_code, external_ref)`.
3. Else fallback dedupe by `(client_id, card_id, occurred_at, amount, volume_liters, merchant_key)`.
   - `merchant_key` is derived from `merchant_name` or `station_id` via `normalize_merchant_key()` in `app/integrations/fuel/normalize.py`.

**Idempotency:** ingest requests are idempotent per `FleetIngestRequestIn.idempotency_key` (unique on `FuelIngestJob`).

### Statement (ProviderStatement → CanonicalStatement)

#### CanonicalStatement fields (mapping target)
Source: `app/integrations/fuel/normalize.py`

- `provider_code` (str, REQUIRED)
- `provider_statement_id` (str | None)
- `period_start` (datetime, REQUIRED)
- `period_end` (datetime, REQUIRED)
- `currency` (str, REQUIRED)
- `total_in` (Decimal | None)
- `total_out` (Decimal | None)
- `closing_balance` (Decimal | None)
- `lines` (list[dict] | None)
- `raw_payload` (dict | None)

#### Example JSON (ProviderStatement)

```json
{
  "provider_statement_id": "stmt-2024-06",
  "period_start": "2024-06-01T00:00:00Z",
  "period_end": "2024-06-30T23:59:59Z",
  "currency": "RUB",
  "total_in": "0",
  "total_out": "125000.00",
  "closing_balance": "0",
  "lines": [
    {"provider_tx_id": "tx-984312", "amount": "1850.50"}
  ],
  "raw_payload": {"provider_period": "2024-06"}
}
```

#### Statement dedupe

Statements are deduped by `source_hash` computed from canonical statement fields in `store_statement()` (`app/integrations/fuel/jobs.py`).

---

## A4. Poll / Backfill / Replay Semantics

Source: `app/integrations/fuel/jobs.py`.

### Poll

- **Method:** `fetch_transactions(conn, since, until, cursor)`.
- **Expected ordering:** by `occurred_at` ascending (preferred). Out-of-order is allowed but increases dedupe load.
- **Delivery guarantee:** at-least-once.
- **Cursor:** `TxPage.next_cursor` is persisted in `FuelProviderConnection.last_sync_cursor`.

### Backfill

- Implemented in `backfill_provider()`.
- Time range split into windows (`batch_hours`, default `24` hours).
- Each window uses the same poll flow and dedupe rules.

### Replay

- Implemented in `replay_raw_event()`.
- Replays a single stored raw event (`FuelProviderRawEvent`) by calling `map_raw_event()`.
- **Idempotency:** uses a new `idempotency_key` per replay job; transaction dedupe still applies.

### Raw event storage

Raw events are stored in `FuelProviderRawEvent` with:

- `provider_event_id` (unique per provider if present).
- `payload_redacted` and `payload_hash` (see `redact_payload()` / `payload_hash()` in `normalize.py`).

### Dedupe rules (summary)

See A3 for detailed dedupe logic. Providers must ensure `provider_tx_id` is stable and unique when possible.

---

## A5. Error Handling & Retries

### Error classes

NEFT classifies provider errors for retry as follows (see `docs/integrations/fuel/PROVIDER_ERROR_CODES.md`):

- **Transient (retry)**: timeouts, rate limits, temporary provider errors.
- **Permanent (no retry)**: schema invalid, auth failed, invalid request.

### Retry policy

- **Core retry strategy:** NOT IMPLEMENTED in `FuelProviderConnector`. Retries are handled by the caller/job runner.
- **Provider adapter:** should implement exponential backoff for transient errors and surface error codes.

### Timeouts

- **Provider client timeouts:** NOT IMPLEMENTED in core. Must be enforced in provider implementations.
- **Known timeout in core:** `requests.get(..., timeout=30)` for EDI payload URLs in `app/integrations/fuel/jobs.py`.

### Circuit breaker

- NOT IMPLEMENTED in provider core.

---

## A6. SLA / Performance Contract (v1)

These are **provider obligations** for v1 compatibility. Enforcement is NOT IMPLEMENTED in core.

| Operation | Target | Notes |
| --- | --- | --- |
| `health()` | ≤ 1s | Partner must respond quickly for monitoring. |
| `fetch_transactions()` | ≤ 30s for a 24h window | Must support pagination to keep batch size reasonable. |
| `fetch_statements()` | ≤ 30s per period | Optional by integration flow. |
| Page size | ≤ 1,000 items per page | Provider should paginate; NEFT accepts `next_cursor`. |

If provider limits differ, they **must** be documented in the integration runbook.

---

## A7. Security Requirements

### Authentication options

Providers may use one of the following (see `FuelProviderAuthType` in `app/integrations/fuel/models.py`):

- `API_KEY`
- `OAUTH2`
- `EDI`

### Secret storage

- Secrets **must not** be hardcoded.
- Use `secret_ref` in `FuelProviderConnection` and store secrets in the configured secret manager (env/vault).

### Data minimization

- **No PII** beyond what is required for mapping.
- Raw payloads are stored in **redacted** form via `redact_payload()`.

### Integrity (optional)

- If provider supports payload signing or hashing, include signature metadata in `raw_payload` and verify before mapping.

---

## A8. Conformance Tests

See `docs/integrations/fuel/PROVIDER_CONFORMANCE_CHECKLIST.md` for the full checklist. Minimum tests:

- **Happy path**: stations/prices are NOT IMPLEMENTED; transactions + statements succeed.
- **Duplicate transaction**: same `provider_tx_id` produces `deduped_count` increment.
- **Out-of-order**: transaction order does not break ingest.
- **Missing fields**: `occurred_at`, `amount`, `currency` are validated by provider mapping.
- **Replay**: `map_raw_event()` replays a stored event without creating a duplicate.

---

## Appendix: NOT IMPLEMENTED

The following expected capabilities are not present in the current provider interface:

- `fetch_stations()`, `map_station()`
- `fetch_prices()`, `map_product()`

Providers **must not** implement these in v1 integrations. If the interface changes, this document will be updated.

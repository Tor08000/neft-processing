# NEFT Platform — Event Catalog (AS-IS)

> **Source of truth:** event tables and services in `platform/processing-core/app/models`, `platform/processing-core/app/services`, and `platform/integration-hub/neft_integration_hub/*`.

## 1) Core event streams (processing_core schema)

| Event stream / table | Source (writes) | Consumers (reads) | Payload / schema | Notes |
|---|---|---|---|---|
| `case_events` | Case services (`app/services/cases_service.py`, `app/services/case_events_service.py`, `app/services/fleet_service.py`, `app/services/billing_service.py`, `app/services/service_booking_service.py`) | Admin/client portals, audit/ops tooling | `CaseEvent` with `type`, `payload_redacted`, hash/signature fields. (`platform/processing-core/app/models/cases.py`) | Hash-chain + signature fields; immutable sequence with `ux_case_events_case_seq`. |
| `marketplace_order_events` | `app/services/marketplace_order_service.py` | Client/partner marketplace flows | `MarketplaceOrderEvent` with `event_type` enum. (`platform/processing-core/app/models/marketplace_orders.py`) | Immutable via ORM event hooks. |
| `service_booking_events` | `app/services/service_booking_service.py` | Booking flows + case linkage | `ServiceBookingEvent` with `event_type` enum. (`platform/processing-core/app/models/service_bookings.py`) | Immutable via ORM event hooks. |
| `service_proof_events` | `app/services/service_completion_proof_service.py` | Booking proofs, dispute resolution | `ServiceProofEvent` with `event_type` enum. (`platform/processing-core/app/models/service_completion_proofs.py`) | Immutable via ORM event hooks. |
| `money_flow_events` | `app/services/money_flow/*` | Billing/finance | `MoneyFlowEventType` enum. (`platform/processing-core/app/models/money_flow.py`, `platform/processing-core/app/services/money_flow/events.py`) | Links to money flows. |
| `payout_events` | `app/services/settlement_service.py`, `app/services/payouts_service.py` | Finance ops | `PayoutEvent` with `event_type` text. (`platform/processing-core/app/models/payout_event.py`) | Associated with `payout_orders`. |
| `dispute_events` | `app/services/operations_scenarios/disputes.py` | Finance ops | `DisputeEventType` enum. (`platform/processing-core/app/models/dispute.py`) | Tracks dispute lifecycle. |
| `marketplace_events` | `app/services/marketplace_recommendation_service.py` | Recommendations pipeline | `MarketplaceEventType` enum. (`platform/processing-core/app/models/marketplace_recommendations.py`) | Behavioral/event log for recommendations. |
| `sponsored_events` | `app/services/marketplace_sponsored_service.py` | Sponsored analytics | `SponsoredEventType` enum. (`platform/processing-core/app/models/marketplace_sponsored.py`) | Tracks impressions/clicks/spend. |
| `logistics_tracking_events` / `logistics_deviation_events` | `app/services/logistics/*` | Logistics UI/reporting | `LogisticsTrackingEventType` / `LogisticsDeviationEventType`. (`platform/processing-core/app/models/logistics.py`) | Time-series tracking + deviations. |
| `fuel_card_status_events` | Fleet ingestion & card lifecycle (`app/services/fleet_service.py`) | Fleet UI | Status change events. (`platform/processing-core/app/models/fuel.py`) | Immutable status history. |
| `fuel_anomaly_events` | `app/services/fleet_anomaly_service.py` | Fleet ops | Event log for anomalies. (`platform/processing-core/app/models/fuel.py`) | Links to detection rules. |
| `fleet_notification_outbox` | `app/services/fleet_notification_dispatcher.py` | Notification dispatcher | Notification payload/metadata. (`platform/processing-core/app/models/fuel.py`) | Used to deliver email/telegram/webpush. |
| `bi_order_events` / `bi_payout_events` / `bi_decline_events` | `app/services/bi/metrics.py` | BI export/reporting | Aggregated BI event records. (`platform/processing-core/app/models/bi.py`) | ClickHouse optional. |

## 2) Integration Hub events (integration-hub DB)

| Event stream / table | Source (writes) | Consumers (reads) | Payload / schema | Notes |
|---|---|---|---|---|
| `webhook_intake_events` | `neft_integration_hub/services/webhook_intake.py` | Audit/monitoring | Intake metadata + payload. (`platform/integration-hub/neft_integration_hub/models/webhook_intake.py`) | Records signature verification state. |
| `webhook_deliveries` | `neft_integration_hub/services/webhooks.py` | Webhook worker | Delivery attempts, retries. (`platform/integration-hub/neft_integration_hub/models/webhooks.py`) | Tracks SLA, retry state. |
| `webhook_alerts` | `neft_integration_hub/services/webhooks.py` | Ops | SLA/alert state. (`platform/integration-hub/neft_integration_hub/models/webhooks.py`) | Alert types include SLA breach and delivery failure. |
| `edo_documents` / `edo_stub_messages` | `neft_integration_hub/services/edo_stub.py`, `neft_integration_hub/services/edo_service.py` | Integration hub API | EDO document lifecycle. (`platform/integration-hub/neft_integration_hub/models/edo.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py`) | Explicit stub remains available; live defaults are real/degraded, not mock-by-default. |
| Log-based EDO event envelope | `neft_integration_hub/events.py` | Log aggregation | JSON log envelope `EventEnvelope`. (`platform/integration-hub/neft_integration_hub/events.py`) | Emitted via logger `edo.event`. |

## 3) Event payload references

- **Case events payload**: `CaseEvent.payload_redacted` JSON column. (`platform/processing-core/app/models/cases.py`)
- **Webhook delivery payload**: `webhook_deliveries.payload` JSON column. (`platform/integration-hub/neft_integration_hub/models/webhooks.py`)
- **Integration hub intake payload**: `webhook_intake_events.payload` JSON column. (`platform/integration-hub/neft_integration_hub/models/webhook_intake.py`)

## 4) NOT IMPLEMENTED

- No Kafka/RabbitMQ-based event bus is defined in compose or code. **NOT IMPLEMENTED**.
- No out-of-process event schema registry is defined. **NOT IMPLEMENTED**.

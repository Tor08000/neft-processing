# On-demand integrations status

## Definitions

- **NOT CONNECTED**: no external provider connection is active in runtime, but the integration surface is prepared.
- **READY TO CONNECT**: contracts exist, endpoints are implemented, and a local stub is available for testing.

## Integration status table

| Integration | Status | Where | How to enable | Contracts | Notes |
| --- | --- | --- | --- | --- | --- |
| Bank API | NOT CONNECTED | integration-hub (stub available) | `BANK_PROVIDER=stub` | OpenAPI v1 | No real bank connection in runtime. |
| ERP/1C | NOT CONNECTED | erp_stub + integration-hub | `ERP_PROVIDER=stub` | Export format v1 | Stub export pipeline only. |
| EDO (Diadoc/Contour) | NOT CONNECTED | integration-hub EDO stub | `EDO_PROVIDER=stub` | EDO API v1 | Status simulation supported. |
| Fuel Networks | NOT CONNECTED | provider framework + virtual network | `FUEL_PROVIDER=virtual` | Provider Standard v1 | Local virtual network for testing. |
| SMS | NOT CONNECTED | sms_stub | `SMS_PROVIDER=stub` | Notify API | Stub only. |
| Voice | NOT CONNECTED | voice_stub | `VOICE_PROVIDER=stub` | Notify API | Stub only. |
| Webhooks | READY TO CONNECT | integration-hub endpoints + HMAC spec | enable endpoints + secrets | Webhook Signature v1 | Intake + registry + test delivery. |

## Contracts, secrets, and networks

- **Contracts**: follow the per-integration contract listed above (OpenAPI v1, Export v1, EDO API v1, Webhook Signature v1).
- **Secrets**: provide HMAC secrets for webhooks (`WEBHOOK_INTAKE_SECRET`) and per-provider credentials as needed.
- **Networks**: allow outbound access from the integration hub to partner endpoints when enabling real providers.

## Mock/stub modes

- **EDO stub**: `/api/int/v1/edo/send`, `/api/int/v1/edo/{edo_doc_id}/status`, `/api/int/v1/edo/{edo_doc_id}/simulate`.
- **Webhook intake stub**: `/api/int/v1/webhooks/client/events`, `/api/int/v1/webhooks/partner/events` with optional unsigned mode (`WEBHOOK_ALLOW_UNSIGNED=true`).
- **Webhook registry/test delivery**: `/api/int/v1/webhooks/endpoints`, `/api/int/v1/webhooks/endpoints/{id}/test`.

## Run instructions

1. **Start the stack**:
   ```bash
   docker compose up -d integration-hub gateway postgres redis minio
   ```
2. **Check health via gateway**:
   ```bash
   curl -fsS http://localhost/api/int/health
   ```
3. **Send an EDO stub document**:
   ```bash
   curl -fsS http://localhost/api/int/v1/edo/send \
     -H "Content-Type: application/json" \
     -d '{"doc_id":"doc-1","counterparty":{"inn":"7700000000"},"payload_ref":"s3://stub/doc-1"}'
   ```
4. **Check EDO status / simulate signed**:
   ```bash
   curl -fsS http://localhost/api/int/v1/edo/<edo_doc_id>/status
   curl -fsS http://localhost/api/int/v1/edo/<edo_doc_id>/simulate \
     -H "Content-Type: application/json" \
     -d '{"status":"SIGNED"}'
   ```
5. **Send a webhook intake event**:
   ```bash
   curl -fsS http://localhost/api/int/v1/webhooks/client/events \
     -H "Content-Type: application/json" \
     -d '{"event_type":"test.event","payload":{"id":"evt-1"}}'
   ```

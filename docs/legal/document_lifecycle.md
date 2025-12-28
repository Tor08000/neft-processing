# Document Lifecycle (v1)

This document describes the legally correct lifecycle for client documents in core-api.

## Document types (contract)

- `INVOICE`
- `ACT`
- `RECONCILIATION_ACT`
- `CLOSING_PACKAGE`
- `OFFER`

## Statuses (immutable)

`DRAFT → ISSUED → ACKNOWLEDGED → FINALIZED → VOID`

| Status | Meaning | Notes |
| --- | --- | --- |
| `DRAFT` | Calculation only, not a legal document | No client actions. |
| `ISSUED` | Document is formed, number/date assigned | Client can download and acknowledge. |
| `ACKNOWLEDGED` | Client confirmed receipt/acceptance | Immutable intent is recorded as an event. |
| `FINALIZED` | Legal state, immutable | May be finalized only after ACK. |
| `VOID` | Annulled | Recorded as a separate audit event. |

## Rules

- **Single source of truth:** core-api owns the canonical document state.
- **No edits after ACK/FINALIZED:** any attempted mutation must return `409` and produce an audit event.
- **document_acknowledgement is an event:** confirmation does not modify document content.
- **Signing is not a document mutation:** signatures are stored as separate events/records.
- **Risk-based decisioning is applied as part of automated compliance control.**

## Events (audit)

Required public audit events:

- `DOCUMENT_ISSUED`
- `DOCUMENT_SENT`
- `DOCUMENT_ACKNOWLEDGED`
- `DOCUMENT_FINALIZED`
- `DOCUMENT_VOIDED`
- `DOCUMENT_OVERRIDE`
- `CLOSING_PACKAGE_FINALIZED` (closing_package lifecycle)

Each event must record: actor, timestamp, reason (if present), and hash snapshot (hash + prev_hash).

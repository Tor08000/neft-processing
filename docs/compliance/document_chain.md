# Document Hash Chain

## Purpose

The document chain ensures legal immutability and traceability for all client documents. Each record carries a hash that is derived from document content and metadata and is anchored with audit events.

## Hash composition

Each document hash (`document_hash`) includes:

- Document content (PDF/XLSX bytes)
- Key metadata (type, number, period, version)
- Previous hash (when version > 1)

## Acknowledgement hash

When a document is acknowledged, the system derives an acknowledgement hash:

```
ack_hash = sha256(document_hash + ack_timestamp + ack_actor)
```

This hash is persisted in the audit log to prove document_acknowledgement without mutating document content.

## Immutability enforcement

- After `ACKNOWLEDGED` or `FINALIZED`, any mutation attempt returns **409** and produces a public audit event.
- Audit records are chained via `hash`/`prev_hash` for tamper evidence.

## Required data for legal acknowledgement

- `user_id` / `email`
- timestamp
- IP + user_agent
- document hash
- immutable audit record

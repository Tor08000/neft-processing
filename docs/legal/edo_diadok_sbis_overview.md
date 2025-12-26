# ЭДО (Диадок/СБИС) overview

```mermaid
sequenceDiagram
    participant Core as NEFT Core
    participant Adapter as EDO Adapter
    participant EDO as Diadok/SBIS

    Core->>Adapter: send_for_signing(document_id, payload)
    Adapter->>EDO: Create document package
    EDO-->>Adapter: external_id + status
    Adapter-->>Core: EnvelopeRef(SENT)
    Core->>Core: Save document_envelopes
    Core->>Adapter: poll/get_status(external_id)
    Adapter-->>Core: EnvelopeStatus(SIGNED)
    Core->>Adapter: fetch_signed_artifacts
    Adapter-->>Core: EDI XML/PDF + signatures
    Core->>Core: Store document_files + document_signatures
```

## Data model summary
- Same `document_envelopes`/`document_signatures` tables used for EDI.
- `document_files` supports `EDI_XML` file type.

## Security notes
- External IDs are unique per provider.
- Webhook signatures validated per provider (future).

## SLA for statuses
- Provider dependent; poll or webhook frequency defined in ops runbook.

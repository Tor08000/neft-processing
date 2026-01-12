# CLIENT 06 — Monthly Documents (Invoice / Act / Reconciliation)

## Goal
Client downloads monthly documents and acknowledges receipt/signature.

## Actors & Roles
- Client Owner / Client Accountant

## Prerequisites
- Billing runs completed for period.
- Document templates available in document-service.

## UI Flow
**Client portal**
- Invoices list → invoice details → download PDF → acknowledge receipt.
- Closing packages list → package details → acknowledge package.

## API Flow
1. `GET /api/v1/client/invoices?date_from=...&date_to=...` — list invoices.
2. `GET /api/v1/client/invoices/{invoice_id}` — invoice details.
3. `GET /api/v1/client/invoices/{invoice_id}/pdf` — download PDF.
4. `POST /api/v1/client/documents/INVOICE_PDF/{invoice_id}/ack` — acknowledge document.
5. `POST /api/v1/admin/closing-packages` — generate closing package (admin).
6. `POST /api/v1/admin/closing-packages/{id}/finalize` — finalize closing package.
7. `POST /api/v1/client/closing-packages/{id}/ack` — acknowledge closing package.
8. `GET /api/v1/admin/integrations/onec/exports/{id}/download` — download 1C XML export.

## DB Touchpoints
- `documents`, `document_files` — generated documents.
- `closing_packages` — package metadata.
- `document_acknowledgements` — client acknowledgements.

## Events & Audit
- `INVOICE_ISSUED` — billing period issuance.
- `DOCUMENT_ACKNOWLEDGED` — audit event on acknowledgements.
- `ONEC_EXPORT_COMPLETED` — export artifacts recorded in audit log.

## Security / Gates
- Client portal auth required; audit event recorded on forbidden access.

## Failure modes
- Invoice not found or belongs to another client → `404` / `403`.
- Missing PDF hash → `409 document_hash_missing` (ack blocked).

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_billing_invoice_pdf_e2e.py`, `platform/processing-core/app/tests/test_closing_documents_e2e.py`.
- smoke cmd: `scripts/smoke_closing_package.cmd` (placeholder).
- PASS: invoice PDF available and acknowledgement stored.

# CLIENT 06 — Monthly Documents (Invoice / Act / Reconciliation)

## Goal
Client downloads monthly documents and acknowledges receipt/signature.

## Actors & Roles
- Client Owner / Client Accountant

## Prerequisites
- Billing runs completed for period.
- Invoice PDF available.

## UI Flow
**Client portal**
- Invoices list → invoice details → download PDF → acknowledge receipt.

**NOT IMPLEMENTED**
- Closing packages page and bundled invoice/act/recon package UI.

## API Flow
1. `GET /api/v1/client/invoices?date_from=...&date_to=...` — list invoices.
2. `GET /api/v1/client/invoices/{invoice_id}` — invoice details.
3. `GET /api/v1/client/invoices/{invoice_id}/pdf` — download PDF.
4. `POST /api/v1/client/documents/INVOICE_PDF/{invoice_id}/ack` — acknowledge document.
5. `GET /api/v1/admin/integrations/onec/exports` — list 1C exports for monthly package (admin).
6. `GET /api/v1/admin/integrations/onec/exports/{id}/download` — download NEFT_1C_EXCHANGE XML.

**NOT IMPLEMENTED**
- Closing packages endpoints (`/closing-packages`, `/documents/{id}/download`, `/closing-packages/{id}/sign`).

## DB Touchpoints
- `invoices` — invoice records.
- `invoice_payments`, `credit_notes` — invoice payments/refunds.
- `document_acknowledgements` — client acknowledgements of documents.

## Events & Audit
- `INVOICE_ISSUED` — case event emitted during billing.
- `DOCUMENT_ACKNOWLEDGED` — audit event on document acknowledgement.
- `ONEC_EXPORT_COMPLETED` — audit event for 1C export artifacts.
- **NOT IMPLEMENTED**: `CLOSING_PACKAGE_READY`, `DOC_DOWNLOADED`, `CLOSING_ACK`, `CLOSING_SIGNED`.

## Security / Gates
- Client portal auth required; audit event recorded on forbidden access.

## Failure modes
- Invoice not found or belongs to another client → `404` / `403`.
- Missing PDF hash → `409 document_hash_missing` (ack blocked).

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_billing_invoice_pdf_e2e.py` (invoice-to-PDF path).
- smoke cmd: `scripts/smoke_closing_package.cmd` (fails with NOT IMPLEMENTED).
- PASS: invoice PDF available and acknowledgement stored.

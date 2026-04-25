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
4. `POST /api/v1/client/documents/{document_type}/{document_id}/ack` — acknowledge invoice document (`document_type=INVOICE_PDF` for the monthly invoice PDF flow).
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

## Ownership note
- This monthly-documents scenario intentionally uses the typed legacy manual-ack contour for invoice PDFs plus the closing-package acknowledgement route.
- Canonical general docflow for new generic client document discovery/details lives separately on `/api/core/client/documents*` and frontend `/client/documents*`.

## Failure modes
- Invoice not found or belongs to another client → `404` / `403`.
- Missing PDF hash → `409 document_hash_missing` (ack blocked).

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_documents_lifecycle.py`, `platform/processing-core/app/tests/test_document_service_integration.py`, `platform/processing-core/app/tests/test_decision_payload_normalization.py`, `platform/processing-core/app/tests/test_closing_documents_e2e.py`, `platform/processing-core/app/tests/test_billing_invoice_pdf_e2e.py`.
- smoke cmd: `scripts/smoke_closing_package.cmd` (verified on local core stack).
- PASS: generated document files download, each document is acknowledged and finalized, closing package is acknowledged/finalized, billing close-period to invoice-PDF flow succeeds, and persisted statuses/artifacts end in the expected final state.
- `test_closing_documents_e2e.py` and `test_billing_invoice_pdf_e2e.py` now run on isolated table harnesses instead of broad `Base.metadata.create_all(...)`, so they are current verification evidence for the monthly documents contour.

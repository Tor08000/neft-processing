# Verified Matrix

| Scenario | pytest tests | smoke scripts | UI smoke (Playwright) | Prerequisites (docker compose services) | PASS criteria |
|---|---|---|---|---|---|
| CLIENT 01 Registration → Activation | `platform/processing-core/app/tests/test_crm_onboarding.py`, `platform/processing-core/app/tests/test_legal_gate.py` | `scripts/smoke_onboarding_e2e.cmd` | `frontends/e2e/tests/client_onboarding.spec.ts`, `frontends/e2e/tests/client_legal_gate.spec.ts` | `auth-host`, `processing-core`, `db` | Onboarding reaches `FIRST_OPERATION_ALLOWED`, legal gate cleared |
| CLIENT 02 Users & Roles | **NOT IMPLEMENTED** | `scripts/smoke_client_users_roles.cmd` | **NOT IMPLEMENTED** | `auth-host`, `processing-core`, `db` | **NOT IMPLEMENTED** |
| CLIENT 03 Limits Management | **NOT IMPLEMENTED** | `scripts/smoke_limits_apply_and_enforce.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Limit created and breach recorded |
| CLIENT 04 Cards Issue | **NOT IMPLEMENTED** | `scripts/smoke_cards_issue.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Card issued and status updated |
| CLIENT 05 Operations & Explain | **NOT IMPLEMENTED** | `scripts/smoke_operations_explain.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Explain response contains rules/reasons |
| CLIENT 06 Monthly Documents | `platform/processing-core/app/tests/test_billing_invoice_pdf_e2e.py` | `scripts/smoke_closing_package.cmd` | `frontends/e2e/tests/client_month_close.spec.ts` | `processing-core`, `db`, `s3` (or local storage) | Invoice PDF available and acknowledged |
| CLIENT 07 Reconciliation Request | **NOT IMPLEMENTED** | `scripts/smoke_reconciliation_request_sign.cmd` | `frontends/e2e/tests/client_reconciliation.spec.ts` | `processing-core`, `db` | Request → generated result → acknowledged |
| CLIENT 08 Support Request | **NOT IMPLEMENTED** | `scripts/smoke_support_ticket.cmd` | `frontends/e2e/tests/client_support.spec.ts` | `processing-core`, `db` | Case created and closed |
| PARTNER 09 Partner Onboarding | **NOT IMPLEMENTED** | `scripts/smoke_partner_onboarding.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | **NOT IMPLEMENTED** |
| PARTNER 10 Webhooks Self-Service | `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` | `scripts/smoke_partner_webhooks.cmd` | `frontends/e2e/tests/partner_webhooks.spec.ts` | `integration-hub`, `db` | Endpoint created, test delivery stored |
| PARTNER 11 Payouts Batch Export | `platform/processing-core/app/tests/test_payout_exports_e2e.py` | `scripts/smoke_payouts_batch_export.cmd` | `frontends/e2e/tests/partner_payouts.spec.ts` | `processing-core`, `db` | **NOT IMPLEMENTED** |
| PARTNER 12 Partner Documents | **NOT IMPLEMENTED** | `scripts/smoke_partner_documents.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | **NOT IMPLEMENTED** |
| OPS 13 Billing Run | `platform/processing-core/app/tests/test_invoice_state_machine.py` | `scripts/smoke_billing_run.cmd` | `frontends/e2e/tests/admin_ops_billing.spec.ts` | `processing-core`, `db` | Billing run creates invoices |
| OPS 14 Clearing Batch Build | `platform/processing-core/app/tests/test_admin_clearing_api.py` | `scripts/smoke_clearing_batch.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Batch created and operations listed |
| OPS 15 Reconciliation Run | `platform/processing-core/app/tests/test_reconciliation_v1.py` | `scripts/smoke_reconciliation_run.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Reconciliation run completed |
| OPS 16 Dispute / Refund | **NOT IMPLEMENTED** | `scripts/smoke_dispute_refund.cmd` | **NOT IMPLEMENTED** | `processing-core`, `db` | Dispute lifecycle progresses |

# CI merge gate requirements

## Required release gates (ordered)

Release pipeline must enforce the following order. Any failure blocks release tagging.

1. **Static**
   - lint
   - typecheck (if applicable)
   - import stability tests
2. **Migrations**
   - alembic dry-run
   - apply migrations on empty DB
   - rollback (if supported)
3. **Contracts**
   - API schema compatibility
   - BI mart contracts
   - ABAC schema validation
4. **Core tests**
   - `scripts\\test_processing_core_docker.cmd`
5. **Smoke (backend)**
   - `scripts\\smoke_legal_gate.cmd`
   - `scripts\\smoke_billing_v14.cmd`
   - `scripts\\smoke_edo_sbis_send.cmd`
   - `scripts\\smoke_fuel_ingest_batch.cmd`
   - `scripts\\smoke_partner_onboarding.cmd` (or relevant core set)
6. **UI build**
   - Admin/Client/Partner build
   - Playwright UI smoke (headless)

## GitHub settings checklist

1. Go to **Settings → Branches → Branch protection rules**.
2. Edit (or create) the rule for `main`.
3. Under **Require status checks to pass before merging**:
   - Add checks for each stage above.
   - Keep ordering in the workflow pipeline.
4. Save the rule.

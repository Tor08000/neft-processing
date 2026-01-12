# CI merge gate requirements

## Required release gates (ordered)

Release pipeline must enforce the following order. Any failure blocks release tagging.

1. **Static checks**
   - `python scripts\check_enum_policy.py`
   - `python scripts\check_migration_patterns.py`
   - `python scripts\check_db_alignment.py`
   - `python scripts\check_alembic_history.py`
2. **Migrations**
   - `scripts\check_migrations.cmd` (alembic heads + upgrade on empty DB)
3. **Contracts**
   - `scripts\test_core_full.cmd` (contracts + integration + system suites)
4. **Core tests**
   - `scripts\test_processing_core_docker.cmd`
5. **Smoke (backend)**
   - `scripts\smoke_legal_gate.cmd`
   - `scripts\smoke_billing_v14.cmd`
   - `scripts\smoke_edo_sbis_send.cmd`
   - `scripts\smoke_fuel_ingest_batch.cmd`
6. **BI smoke (if enabled)**
   - `scripts\smoke_bi_ops_dashboard.cmd`
   - `scripts\smoke_bi_partner_dashboard.cmd`
   - `scripts\smoke_bi_client_spend_dashboard.cmd`
7. **UI build + smoke**
   - `cd frontends\admin-ui && npm install && npm run build`
   - `cd frontends\client-portal && npm install && npm run build`
   - `cd frontends\partner-portal && npm install && npm run build`
   - `cd frontends\e2e && npm install && npx playwright install && npx playwright test`

## GitHub settings checklist

1. Go to **Settings → Branches → Branch protection rules**.
2. Edit (or create) the rule for `main`.
3. Under **Require status checks to pass before merging**:
   - Add checks for each stage above.
   - Keep ordering in the workflow pipeline.
4. Save the rule.

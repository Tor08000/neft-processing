# Migrations troubleshooting (processing-core)

## Missing `alembic_version_core`

**Symptoms**
- `required tables missing: missing=['alembic_version_core']`
- `alembic_version_core` is only present under `public` or another schema.

**Checks**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -Atc \"select current_schema(), current_setting('search_path')\""

docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -Atc \"select to_regclass('processing_core.alembic_version_core')\""

# Direct postgres container example (explicit credentials)
docker compose exec -T postgres sh -lc "PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d $POSTGRES_DB -Atc \"select to_regclass('processing_core.alembic_version_core')\""
```

**Fix (automated)**
```bash
scripts\db\repair_processing_core.cmd core-api
```

**Fix (manual)**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -c \"CREATE SCHEMA IF NOT EXISTS processing_core;\""

docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini stamp heads"
```

## Orphan type/domain conflict (`DuplicateObject: type \"<table>\" already exists`)

**Symptoms**
- `DuplicateObject: type "client_onboarding_state" already exists`
- Alembic fails on `CREATE TABLE` for a table that does not exist.

**Checks**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -Atc \"select n.nspname, t.typname, t.typtype from pg_type t join pg_namespace n on n.oid=t.typnamespace where n.nspname='processing_core' and t.typname='client_onboarding_state'\""

docker compose exec -T postgres sh -lc "PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d $POSTGRES_DB -Atc \"select n.nspname, t.typname, t.typtype from pg_type t join pg_namespace n on n.oid=t.typnamespace where n.nspname='processing_core' and t.typname='client_onboarding_state'\""
```

**Fix (automated)**
```bash
scripts\db\repair_processing_core.cmd core-api
```

**Fix (manual)**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -c \"DROP DOMAIN IF EXISTS processing_core.client_onboarding_state CASCADE; DROP TYPE IF EXISTS processing_core.client_onboarding_state CASCADE;\""
```

## Multi-head migrations

**Symptoms**
- `alembic heads` prints more than one revision.
- EntryPoint logs report multiple heads.

**Checks**
```bash
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"
```

**Fix**
- Ensure the merge revision is present and applied.
- If a new merge is required, create one:
```bash
docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini merge <head1> <head2>
```

## Schema/search_path mismatch (tables landing in `public`)

**Symptoms**
- `current_schema=public search_path="$user", public`
- Tables created under `public` instead of `processing_core`.

**Checks**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -Atc \"select current_schema(), current_setting('search_path')\""

docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -Atc \"select table_schema, table_name from information_schema.tables where table_name='operations' order by table_schema\""

docker compose exec -T postgres sh -lc "PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d $POSTGRES_DB -Atc \"select current_schema(), current_setting('search_path')\""
```

**Fix**
```bash
docker compose exec -T core-api sh -lc "psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -c \"SET search_path TO processing_core, public;\""
```

## Extra diagnostics

```bash
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"

docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"
```

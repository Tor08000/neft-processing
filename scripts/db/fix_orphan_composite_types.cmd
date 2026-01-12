@echo off
setlocal
echo [fix-orphan-composite-types] dropping orphan composite types on postgres ...
docker compose exec -T postgres sh -lc "psql -v ON_ERROR_STOP=1 -U \"${POSTGRES_USER:-neft}\" -d \"${POSTGRES_DB:-neft}\" -c \"DO \\$\\$ DECLARE r record; BEGIN FOR r IN ( SELECT n.nspname AS schema_name, t.typname AS type_name FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname = 'processing_core' AND t.typtype='c' AND NOT EXISTS ( SELECT 1 FROM pg_class c JOIN pg_namespace n2 ON n2.oid=c.relnamespace WHERE n2.nspname=n.nspname AND c.relname=t.typname AND c.relkind='r' ) ) LOOP EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name); END LOOP; END \\$\\$;\""
endlocal

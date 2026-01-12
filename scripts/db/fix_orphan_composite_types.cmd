@echo off
setlocal
echo [fix-orphan-composite-types] dropping orphan composite types on postgres ...
docker compose exec -T postgres sh -lc "psql -v ON_ERROR_STOP=1 -U \"${POSTGRES_USER:-neft}\" -d \"${POSTGRES_DB:-neft}\" -c \"DO \\$\\$ DECLARE r record; DECLARE rk char; DECLARE dropped int := 0; BEGIN FOR r IN ( SELECT n.nspname AS schema_name, t.typname AS type_name FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname = 'processing_core' AND t.typtype = 'c' ) LOOP SELECT c.relkind INTO rk FROM pg_class c JOIN pg_namespace n2 ON n2.oid = c.relnamespace WHERE n2.nspname = r.schema_name AND c.relname = r.type_name LIMIT 1; IF rk IS NULL OR rk NOT IN ('r','p') THEN RAISE NOTICE 'dropping orphan composite type %.% (relkind=%)', r.schema_name, r.type_name, rk; EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', r.schema_name, r.type_name); dropped := dropped + 1; END IF; END LOOP; RAISE NOTICE 'dropped % orphan composite types', dropped; END \\$\\$;\""
endlocal

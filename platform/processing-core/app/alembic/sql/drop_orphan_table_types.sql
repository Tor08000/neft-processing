DO $$
DECLARE
    record_type RECORD;
BEGIN
    FOR record_type IN
        SELECT t.typname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'processing_core'
          AND t.typtype = 'c'
    LOOP
        IF to_regclass(format('%I.%I', 'processing_core', record_type.typname)) IS NULL THEN
            EXECUTE format('DROP TYPE IF EXISTS %I.%I CASCADE', 'processing_core', record_type.typname);
        END IF;
    END LOOP;
END $$;

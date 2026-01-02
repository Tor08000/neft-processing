DO $$
DECLARE
    table_name text;
    missing text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY['case_events', 'decision_memory', 'fuel_transactions']
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = table_name
              AND t.tgname = table_name || '_worm_update'
        ) THEN
            missing := missing || table_name || ':worm_update;';
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = table_name
              AND t.tgname = table_name || '_worm_delete'
        ) THEN
            missing := missing || table_name || ':worm_delete;';
        END IF;
    END LOOP;

    IF missing <> '' THEN
        RAISE EXCEPTION 'Missing WORM triggers: %', missing;
    END IF;
END $$;

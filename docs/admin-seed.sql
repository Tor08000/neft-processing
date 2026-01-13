-- Idempotent bootstrap for admin user and roles.
-- Replace email/password hash if you override defaults in .env.
-- Usage: psql -h localhost -U neft -d neft -f docs/admin-seed.sql

DO $$
DECLARE
    v_user_id uuid;
BEGIN
    SELECT id INTO v_user_id FROM users WHERE lower(email) = lower('admin@neft.local');

    IF v_user_id IS NULL THEN
        INSERT INTO users (id, email, full_name, password_hash, is_active)
        VALUES (
            gen_random_uuid(),
            'admin@neft.local',
            'Platform Admin',
            '1504d294e7b890e6bce09eb3984c9f25$49ae3a75131b9ba505f9168463992645eada47a7838e61d594f1e37367fe5327',
            TRUE
        )
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        INTO v_user_id;
    END IF;

    IF v_user_id IS NULL THEN
        SELECT id INTO v_user_id FROM users WHERE lower(email) = lower('admin@neft.local');
    END IF;

    IF v_user_id IS NULL THEN
        RAISE NOTICE 'admin user was not created or found';
        RETURN;
    END IF;

    UPDATE users SET is_active = TRUE WHERE id = v_user_id;

    INSERT INTO user_roles (user_id, role_code)
    VALUES (v_user_id, 'ADMIN')
    ON CONFLICT (user_id, role_code) DO NOTHING;

    INSERT INTO user_roles (user_id, role_code)
    VALUES (v_user_id, 'SUPERADMIN')
    ON CONFLICT (user_id, role_code) DO NOTHING;
END $$;

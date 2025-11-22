# services/core-api/app/alembic/versions/20251112_0001_core.py

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251112_0001_core"
down_revision = "2025_11_01_init"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS clients (
        id           BIGSERIAL PRIMARY KEY,
        name         TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'active',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS cards (
        id           BIGSERIAL PRIMARY KEY,
        client_id    BIGINT NOT NULL REFERENCES clients(id),
        pan_hash     TEXT NOT NULL,                -- хэш PAN
        token        TEXT UNIQUE NOT NULL,         -- токен карты внутр. системы
        status       TEXT NOT NULL DEFAULT 'active',
        limit_day    NUMERIC(16,2) NOT NULL DEFAULT 0,
        spent_day    NUMERIC(16,2) NOT NULL DEFAULT 0,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS price_list (
        id           BIGSERIAL PRIMARY KEY,
        product_code TEXT NOT NULL,
        price        NUMERIC(16,4) NOT NULL,
        currency     TEXT NOT NULL DEFAULT 'RUB',
        valid_from   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id              BIGSERIAL PRIMARY KEY,
        ext_id          TEXT,                     -- внешний id из ТСП/АЗС
        idempotency_key TEXT,                     -- для идемпотентности запросов
        type            TEXT NOT NULL,            -- authorize / capture / reverse
        status          TEXT NOT NULL,            -- approved / declined / reversed / captured
        client_id       BIGINT REFERENCES clients(id),
        card_id         BIGINT REFERENCES cards(id),
        amount          NUMERIC(16,2) NOT NULL,
        currency        TEXT NOT NULL DEFAULT 'RUB',
        product_code    TEXT,
        meta            JSONB DEFAULT '{}'::jsonb,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_transactions_idemp
        ON transactions(idempotency_key);

    CREATE TABLE IF NOT EXISTS holds (
        id            BIGSERIAL PRIMARY KEY,
        trans_id      BIGINT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
        card_id       BIGINT NOT NULL REFERENCES cards(id),
        amount        NUMERIC(16,2) NOT NULL,
        currency      TEXT NOT NULL DEFAULT 'RUB',
        status        TEXT NOT NULL,            -- active / captured / reversed / expired
        expires_at    TIMESTAMPTZ NOT NULL,     -- TTL холда
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_holds_card_status
        ON holds(card_id, status);
    """
    )

    # мини-fixture: демо-клиент, карта и цены
    op.execute(
        """
    INSERT INTO clients (name)
    VALUES ('Demo LLC')
    ON CONFLICT DO NOTHING;

    INSERT INTO cards (client_id, pan_hash, token, status, limit_day, spent_day)
    VALUES (
        (SELECT id FROM clients WHERE name = 'Demo LLC'),
        'hash:1111',
        'card_demo_1',
        'active',
        20000,
        0
    )
    ON CONFLICT DO NOTHING;

    INSERT INTO price_list (product_code, price)
    VALUES
        ('AI92', 54.30),
        ('AI95', 59.80),
        ('DT',   62.10)
    ON CONFLICT DO NOTHING;
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS holds;
    DROP TABLE IF EXISTS transactions;
    DROP TABLE IF EXISTS price_list;
    DROP TABLE IF EXISTS cards;
    DROP TABLE IF EXISTS clients;
    """
    )

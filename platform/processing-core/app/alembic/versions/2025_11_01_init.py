# services/core-api/app/alembic/versions/2025_11_01_init.py

revision = "2025_11_01_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Пустая миграция: базовая схема создаётся через db/init/01_schema.sql
    # Alembic просто фиксирует стартовую ревизию.
    pass


def downgrade():
    # Откатывать базовую схему через Alembic не будем.
    pass

# Шаблон отчёта: падение `core-api` на `alembic upgrade`

Используй блоки ниже, чтобы быстро собрать всю информацию по фейлу миграции.

## 1) Одна фраза
```
core-api падает на alembic upgrade
```

## 2) Кусок лога с ошибкой + SQL
Вставь фактический фрагмент лога с трассой и проблемным SQL. Пример:
```
2025-12-01 10:22:33,123 INFO  alembic.runtime.migration  Running upgrade 20251120_0003_limits_rules_v2 -> 20251124_0003_merchants_terminals_cards
2025-12-01 10:22:33,456 INFO  sqlalchemy.engine.Engine  CREATE TABLE merchants (id VARCHAR(64) NOT NULL, name VARCHAR(255) NOT NULL, status VARCHAR(32) NOT NULL, PRIMARY KEY (id))
2025-12-01 10:22:33,789 ERROR sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable) relation "merchants" already exists
```

## 3) Содержимое миграции, на которой падает
`platform/processing-core/app/alembic/versions/20251124_0003_merchants_terminals_cards.py`
```python
"""merchants terminals

Revision ID: 20251124_0003_merchants_terminals_cards
Revises: 20251120_0003_limits_rules_v2
Create Date: 2025-11-24 00:03:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251124_0003_merchants_terminals_cards"
down_revision = "20251120_0003_limits_rules_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_merchants_id", "merchants", ["id"], unique=False)
    op.create_index("ix_merchants_status", "merchants", ["status"], unique=False)

    op.create_table(
        "terminals",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(length=64), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_terminals_id", "terminals", ["id"], unique=False)
    op.create_index("ix_terminals_merchant_id", "terminals", ["merchant_id"], unique=False)
    op.create_index("ix_terminals_status", "terminals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_terminals_status", table_name="terminals")
    op.drop_index("ix_terminals_merchant_id", table_name="terminals")
    op.drop_index("ix_terminals_id", table_name="terminals")
    op.drop_table("terminals")

    op.drop_index("ix_merchants_status", table_name="merchants")
    op.drop_index("ix_merchants_id", table_name="merchants")
    op.drop_table("merchants")
```

## 4) Текущий тип `alembic_version`
Если есть доступ к БД, приложи вывод:
```
docker compose exec -T postgres psql -U postgres -d neft -c "\d alembic_version"
```
(Нужен тип столбца `version_num` и первичный ключ.)

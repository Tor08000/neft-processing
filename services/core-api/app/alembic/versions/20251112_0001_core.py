"""core legacy migration (disabled)

Эта миграция изначально создавала прототипные таблицы:
clients / cards / price_list / transactions / holds
со старыми типами (BIGINT и т.д.).

Сейчас базовая схема уже развернута отдельно (через 01_schema.sql),
таблицы имеют другие типы (UUID / VARCHAR и т.п.), а сами эти прототипные
таблицы нам не нужны.

Чтобы сохранить линейную историю Alembic и не ломать существующую БД,
делаем эту миграцию 'пустой' (no-op).
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = "20251112_0001_core"
down_revision = "2025_11_01_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op.

    Ничего не создаём и не меняем. База уже приведена к актуальной схеме
    другими средствами и последующими миграциями.
    """
    pass


def downgrade() -> None:
    """No-op.

    Не пытаемся ничего откатывать, так как эта ревизия не вносит изменений.
    """
    pass

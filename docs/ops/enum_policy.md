# Enum Policy (Postgres / Alembic / SQLAlchemy)

## Цель

Запретить неидемпотентное создание PostgreSQL ENUM и зафиксировать единый безопасный паттерн для миграций и моделей.

## Запрещено

- Alembic миграции с `sa.Enum(..., name="...")`.
- Alembic миграции с `postgresql.ENUM(..., name="...", create_type=True)` или без `create_type=False`.
- Создание ENUM без `schema` (нужно явно указывать схему).
- Прямой `op.execute("CREATE TYPE ...")` без safe helper.

## Разрешено

- Только safe helpers в миграциях:
  - `ensure_pg_enum(schema, name, values)`
  - `ensure_pg_enum_value(schema, name, value)`
- В моделях SQLAlchemy:
  - `postgresql.ENUM(..., create_type=False, schema=SCHEMA)`

## Как добавлять новое значение enum (паттерн миграции)

```python
from alembic import op
from app.alembic.utils import ensure_pg_enum_value
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum_value(bind, "invoice_status", "CANCELLED", schema=SCHEMA)
```

## Почему это важно

- `DuplicateObject` в PostgreSQL при повторных прогонах.
- Неидемпотентные миграции ломают CI/rollout.
- Safe helpers обеспечивают повторяемость и корректный контроль схем.

## Enforcement

- Скрипт `scripts/check_enum_policy.py` проверяет миграции и модели.
- Pre-commit hook `neft-enum-policy` должен быть включён локально.
- CI workflow `Enum Policy` должен быть **required** для merge.

# Codex task template (migrations)

Use this template when writing migration-related tasks.

## Task
- Describe the schema change and target migration file.

## Migration Implementation Rules

Use only app/alembic/utils.py helpers for indexes/constraints/enums.

Do not use raw SQL for CREATE INDEX.

If expression index needed, use create_unique_expr_index_if_not_exists.

Always compile migrations: python -m py_compile <file>.

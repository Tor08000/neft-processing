# Migration patterns

Use the blocks below verbatim in new migrations.

## Add a column (idempotent)
```python
if not column_exists(bind, "table", "col", schema=SCHEMA):
    op.add_column("table", sa.Column("col", sa.String(64), nullable=True), schema=SCHEMA)
```

## Add enum + values (idempotent)
```python
ensure_pg_enum(bind, "my_enum", ["A","B"], schema=SCHEMA)
ensure_pg_enum_value(bind, "my_enum", "A", schema=SCHEMA)
```

## Create index (idempotent)
```python
create_index_if_not_exists(bind, "ix_table_col", "table", ["col"], schema=SCHEMA)
```

## Create UNIQUE index (idempotent)
```python
create_unique_index_if_not_exists(bind, "uq_table_col", "table", ["col"], schema=SCHEMA)
```

## Create UNIQUE expression index (idempotent)
```python
create_unique_expr_index_if_not_exists(bind, "uq_expr", "table", "(COALESCE(x,''), y)", schema=SCHEMA)
```

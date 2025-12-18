@echo off
setlocal
if "%1"=="" (
  set TARGET=core-api
) else (
  set TARGET=%1
)

echo [diag-db] collecting inventory from %TARGET% ...
docker compose exec -T %TARGET% sh -lc "python - <<'PY'
from app.diagnostics.db_state import collect_inventory
inv = collect_inventory()
print(f'server={inv.server_addr}:{inv.server_port} db={inv.current_database} user={inv.current_user}')
print(f'search_path={inv.search_path}')
print(f'schemas={inv.schemas}')
print(f'alembic_versions={inv.alembic_versions}')
print(f'tables={[(s, t) for s, t in inv.tables[:30]]}')
print(f'missing_tables={inv.missing_tables()}')
PY"
endlocal

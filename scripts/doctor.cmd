@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
set "FAIL=0"

call :run "postgres reachable" "docker compose -f %COMPOSE_FILE% exec -T postgres pg_isready -U neft -d neft"
call :run "auth-host DB creds usable" "docker compose -f %COMPOSE_FILE% exec -T auth-host python -c \"import psycopg,os; dsn=f'postgresql://{os.getenv('POSTGRES_USER','neft')}:{os.getenv('POSTGRES_PASSWORD','change-me')}@{os.getenv('POSTGRES_HOST','postgres')}:{os.getenv('POSTGRES_PORT','5432')}/{os.getenv('POSTGRES_DB','neft')}'; c=psycopg.connect(dsn); c.execute('select 1'); c.close()\""
call :run "processing_core schema exists" "docker compose -f %COMPOSE_FILE% exec -T core-api python -c \"from app.db import get_sessionmaker; from sqlalchemy import text; db=get_sessionmaker()(); n=db.execute(text(\"select count(*) from information_schema.schemata where schema_name='processing_core'\")).scalar_one(); db.close(); assert n==1\""
call :run "demo users exist" "docker compose -f %COMPOSE_FILE% exec -T auth-host python -c \"from app.db import get_conn; import asyncio; async def m():\n async with get_conn() as (_,cur):\n  await cur.execute(\"select count(*) as c from users where lower(email) in ('admin@example.com','partner@neft.local','client@neft.local')\"); r=await cur.fetchone(); assert int(r['c'])==3\nasyncio.run(m())\""
call :run "demo core entities exist" "docker compose -f %COMPOSE_FILE% exec -T core-api python -c \"from app.db import get_sessionmaker; from sqlalchemy import text; db=get_sessionmaker()(); q='''select (select count(*) from processing_core.clients)>0 and (select count(*) from processing_core.accounts)>0 and (select count(*) from processing_core.partner_accounts)>0 and (select count(*) from processing_core.client_users)>0 and (select count(*) from processing_core.client_user_roles)>0 and (select count(*) from processing_core.partner_user_roles)>0'''; ok=db.execute(text(q)).scalar_one(); db.close(); assert ok is True\""

call :run "version table rows" "docker compose -f %COMPOSE_FILE% exec -T postgres psql -U neft -d neft -tA -c \"select count(*) from processing_core.alembic_version_core;\""
call :run "alembic current" "docker compose -f %COMPOSE_FILE% exec -T core-api alembic -c /app/app/alembic.ini current"
call :run "alembic heads" "docker compose -f %COMPOSE_FILE% exec -T core-api alembic -c /app/app/alembic.ini heads"
call :run "decision mode" "docker compose -f %COMPOSE_FILE% exec -T core-api sh -lc \"echo ALEMBIC_DECISION=${ALEMBIC_DECISION:-UNSET}\""

if "%FAIL%"=="0" (
  echo [OK] doctor checks passed
  exit /b 0
)

echo [FAIL] doctor detected issues
exit /b 1

:run
set "NAME=%~1"
set "CMD=%~2"
%CMD% >NUL 2>&1
if errorlevel 1 (
  echo FAIL: %NAME%
  set "FAIL=1"
) else (
  echo OK: %NAME%
)
exit /b 0

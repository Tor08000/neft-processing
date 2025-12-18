@echo off
setlocal
echo [reset-db] stopping stack and dropping volumes...
docker compose down -v

echo [reset-db] starting postgres and redis...
docker compose up -d postgres redis

echo [reset-db] waiting for postgres to accept connections...
docker compose exec -T postgres sh -lc "until pg_isready -U ${POSTGRES_USER:-neft} -d ${POSTGRES_DB:-neft}; do sleep 1; done"

echo [reset-db] applying migrations...
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini upgrade head"

echo [reset-db] verifying schema...
call %~dp0diag-db.cmd core-api
endlocal

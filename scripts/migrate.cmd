@echo off
setlocal
echo [migrate] running alembic upgrade head in core-api container...
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini upgrade head"
endlocal

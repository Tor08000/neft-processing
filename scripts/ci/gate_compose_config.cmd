@echo off
setlocal

if exist docker-compose.dev.yml (
  docker compose -f docker-compose.yml -f docker-compose.dev.yml config >nul
) else (
  docker compose -f docker-compose.yml config >nul
)
if errorlevel 1 exit /b 1

endlocal

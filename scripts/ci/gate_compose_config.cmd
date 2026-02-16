@echo off
setlocal

docker compose -f docker-compose.yml -f docker-compose.dev.yml config >nul
if errorlevel 1 exit /b 1

endlocal

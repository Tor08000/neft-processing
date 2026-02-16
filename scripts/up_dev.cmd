@echo off
setlocal

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
if errorlevel 1 exit /b 1

docker compose ps
if errorlevel 1 exit /b 1

endlocal

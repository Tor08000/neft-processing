@echo off
setlocal

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build ^
  postgres redis minio gateway core-api auth-host ai-service crm-service logistics-service workers beat flower
if errorlevel 1 exit /b 1

docker compose ps
if errorlevel 1 exit /b 1

endlocal

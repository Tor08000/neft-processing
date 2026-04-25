@echo off
setlocal

rem Launch-gate runtime overrides are intentionally non-secret. They keep local
rem .env files from downgrading sandbox/BI proof without writing secrets to disk.
set "BI_CLICKHOUSE_ENABLED=1"
set "DIADOK_MODE=sandbox"
set "SBIS_MODE=sandbox"
set "NOTIFICATIONS_MODE=sandbox"
set "EMAIL_PROVIDER_MODE=sandbox"
set "OTP_PROVIDER_MODE=sandbox"
set "BANK_API_MODE=sandbox"
set "ERP_1C_MODE=sandbox"
set "FUEL_PROVIDER_MODE=sandbox"
set "LOGISTICS_PROVIDER_MODE=sandbox"

docker compose up -d --build integration-hub logistics-service core-api gateway clickhouse clickhouse-init partner-web client-web admin-web
exit /b %ERRORLEVEL%

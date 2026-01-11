@echo off
setlocal

if "%DATABASE_URL%"=="" (
  echo DATABASE_URL is not set
  exit /b 1
)

if "%1"=="" (
  echo Usage: smoke_fuel_offline_reconcile.cmd ^<client_id^> ^<YYYY-MM^>
  exit /b 1
)

if "%2"=="" (
  echo Usage: smoke_fuel_offline_reconcile.cmd ^<client_id^> ^<YYYY-MM^>
  exit /b 1
)

python -m app.integrations.fuel.providers.provider_ref.cli offline-reconcile --client-id %1 --period %2
endlocal

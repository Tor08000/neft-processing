@echo off
setlocal

if "%DATABASE_URL%"=="" (
  echo DATABASE_URL is not set
  exit /b 1
)

if "%1"=="" (
  echo Usage: smoke_fuel_replay_batch.cmd ^<batch_key^> ^<csv_path^>
  exit /b 1
)

if "%2"=="" (
  echo Usage: smoke_fuel_replay_batch.cmd ^<batch_key^> ^<csv_path^>
  exit /b 1
)

python -m app.integrations.fuel.providers.provider_ref.cli replay-batch --batch-key %1 --csv %2
endlocal

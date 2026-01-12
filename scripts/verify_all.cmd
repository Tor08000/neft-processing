@echo off
setlocal EnableExtensions EnableDelayedExpansion

for /f "tokens=2 delims==" %%I in ('wmic os get LocalDateTime /value') do set dt=%%I
set ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,4%

set LOG_DIR=logs
set SNAPSHOT_DIR=docs\as-is
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set LOG_FILE=%LOG_DIR%\verify_all_%ts%.log
set SNAPSHOT_FILE=%SNAPSHOT_DIR%\STATUS_SNAPSHOT_RUNTIME_%ts%.md
set ERROR_FILE=%LOG_DIR%\verify_all_%ts%_errors.tmp

(
  echo # STATUS SNAPSHOT — RUNTIME %ts%
  echo.
  echo **Generated:** %date% %time%
  echo.
  echo ## Steps
  echo ^| Step ^| Status ^| Details ^|
  echo ^|---^|---^|---^|
) > "%SNAPSHOT_FILE%"

(
  echo verify_all.cmd started at %date% %time%
  echo Timestamp: %ts%
  echo Snapshot: %SNAPSHOT_FILE%
) > "%LOG_FILE%"

del "%ERROR_FILE%" 2>NUL

call :run_cmd "1) Stack up" docker compose up -d
if errorlevel 1 goto finalize

call :wait_for_health "1.1) core-api healthy" core-api 120
if errorlevel 1 goto finalize

call :run_cmd "2.1) Migrations" scripts\migrate.cmd
if errorlevel 1 goto finalize

call :run_cmd "2.2) Alembic heads core-api" docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads --verbose"
if errorlevel 1 goto finalize

call :run_cmd "2.3) Alembic current core-api" docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current -v"
if errorlevel 1 goto finalize

call :run_cmd "2.4) Alembic version table core-api" docker compose exec -T core-api sh -lc "heads=$(alembic -c app/alembic.ini heads --verbose | awk '$1==\"Rev:\"{print $2}'); if [ -z \"${heads}\" ]; then echo \"no heads\"; exit 1; fi; versions=$(psql \"${DATABASE_URL}\" -q -tA -c \"select version_num from processing_core.alembic_version_core\"); if [ -z \"${versions}\" ]; then echo \"no versions\"; exit 1; fi; for head in ${heads}; do echo \"${versions}\" | grep -Fxq \"${head}\" || exit 1; done"
if errorlevel 1 goto finalize

call :check_endpoints "3) Health checks" http://localhost/health http://localhost/api/core/health http://localhost/api/auth/health http://localhost/api/ai/health http://localhost/api/int/health
if errorlevel 1 goto finalize

call :check_endpoints "4) Metrics checks" http://localhost/metrics http://localhost:8001/metrics http://localhost:8010/metrics
if errorlevel 1 goto finalize

call :run_cmd "4.5) Smoke checks" scripts\smoke_all.cmd
if errorlevel 1 goto finalize

call :run_smoke_scripts
if errorlevel 1 goto finalize

call :run_pytest_subset
if errorlevel 1 goto finalize

goto finalize

:run_cmd
set step=%~1
shift
set command=%*
(
  echo.
  echo [!step!] %command%
) >> "%LOG_FILE%"
%command% >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :mark_fail "!step!" "%command%"
  exit /b 1
) else (
  call :mark_ok "!step!" "%command%"
)
exit /b 0

:wait_for_health
set step=%~1
set service=%~2
set timeout=%~3
if "%timeout%"=="" set timeout=120
set elapsed=0
:health_loop
for /f %%I in ('docker compose ps -q %service%') do set container_id=%%I
if not defined container_id (
  call :mark_fail "%step%" "Container ID not found for %service%"
  exit /b 1
)
for /f %%H in ('docker inspect --format="{{.State.Health.Status}}" %container_id%') do set health=%%H
echo [!step!] %service% health=!health! >> "%LOG_FILE%"
if "!health!"=="healthy" (
  call :mark_ok "%step%" "%service% healthy"
  exit /b 0
)
if "!health!"=="unhealthy" (
  call :mark_fail "%step%" "%service% unhealthy"
  exit /b 1
)
timeout /t 2 >NUL
set /a elapsed+=2
if !elapsed! GEQ %timeout% (
  call :mark_fail "%step%" "%service% health check timed out"
  exit /b 1
)
goto health_loop

:check_endpoints
set step=%~1
shift
set failed=0
for %%E in (%*) do (
  echo [!step!] Checking %%E >> "%LOG_FILE%"
  curl -fsS %%E >NUL 2>> "%LOG_FILE%"
  if errorlevel 1 (
    set failed=1
    call :append_error "Endpoint failed: %%E"
  )
)
if !failed! EQU 0 (
  call :mark_ok "!step!" "All endpoints OK"
  exit /b 0
)
call :mark_fail "!step!" "One or more endpoints failed"
exit /b 1

:run_smoke_scripts
set step=5) Smoke scripts
set failed=0
call :run_script_if_exists scripts\test_core_api.cmd
call :run_script_if_exists scripts\test_auth_host.cmd
call :run_script_if_exists scripts\billing_smoke.cmd
call :run_script_if_exists scripts\smoke_billing_finance.cmd
call :run_script_if_exists scripts\smoke_invoice_state_machine.cmd
if !failed! EQU 0 (
  call :mark_ok "%step%" "All smoke scripts OK"
  exit /b 0
)
call :mark_fail "%step%" "One or more smoke scripts missing or failed"
exit /b 1

:run_script_if_exists
set script=%~1
if not exist "%script%" (
  set failed=1
  call :append_error "Missing smoke script: %script%"
  exit /b 0
)
call :run_cmd "5.x) %script%" "%script%"
if errorlevel 1 set failed=1
exit /b 0

:run_pytest_subset
set step=6) Pytest smoke subset
call :run_cmd "6.1) test_transactions_pipeline.py" docker compose exec -T core-api sh -lc "pytest app/tests/test_transactions_pipeline.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :run_cmd "6.2) test_invoice_state_machine.py" docker compose exec -T core-api sh -lc "pytest app/tests/test_invoice_state_machine.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :run_cmd "6.3) test_settlement_v1.py" docker compose exec -T core-api sh -lc "pytest app/tests/test_settlement_v1.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :run_cmd "6.4) test_reconciliation_v1.py" docker compose exec -T core-api sh -lc "pytest app/tests/test_reconciliation_v1.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :run_cmd "6.5) test_documents_lifecycle.py" docker compose exec -T core-api sh -lc "pytest app/tests/test_documents_lifecycle.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :run_cmd "6.6) test_webhooks.py" docker compose exec -T integration-hub sh -lc "pytest neft_integration_hub/tests/test_webhooks.py"
if errorlevel 1 (
  call :mark_fail "%step%" "pytest subset failed"
  exit /b 1
)
call :mark_ok "%step%" "All pytest checks OK"
exit /b 0

:mark_ok
set step=%~1
set details=%~2
echo ^| %step% ^| OK ^| %details% ^| >> "%SNAPSHOT_FILE%"
exit /b 0

:mark_fail
set step=%~1
set details=%~2
echo ^| %step% ^| FAIL ^| %details% ^| >> "%SNAPSHOT_FILE%"
call :append_error "%step% failed: %details%"
exit /b 1

:append_error
echo - %~1 >> "%ERROR_FILE%"
exit /b 0

:finalize
(
  echo.
  echo ## Errors
) >> "%SNAPSHOT_FILE%"
if exist "%ERROR_FILE%" (
  type "%ERROR_FILE%" >> "%SNAPSHOT_FILE%"
) else (
  echo - None >> "%SNAPSHOT_FILE%"
)

if exist "%ERROR_FILE%" (
  echo verify_all.cmd finished with errors at %date% %time% >> "%LOG_FILE%"
  exit /b 1
)

echo verify_all.cmd finished OK at %date% %time% >> "%LOG_FILE%"
exit /b 0

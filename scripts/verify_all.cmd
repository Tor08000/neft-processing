@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ===== Timestamp =====
for /f "tokens=2 delims==" %%I in ('wmic os get LocalDateTime /value') do set "dt=%%I"
set "ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,4%"

REM ===== Paths =====
set "LOG_DIR=logs"
set "SNAPSHOT_DIR=docs\as-is"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%SNAPSHOT_DIR%" mkdir "%SNAPSHOT_DIR%"

set "LOG_FILE=%LOG_DIR%\verify_all_%ts%.log"
set "SNAPSHOT_FILE=%SNAPSHOT_DIR%\STATUS_SNAPSHOT_RUNTIME_%ts%.md"
set "ERROR_FILE=%LOG_DIR%\verify_all_%ts%_errors.tmp"

del "%ERROR_FILE%" 2>NUL

REM ===== Snapshot header =====
(
  echo # STATUS SNAPSHOT — RUNTIME %ts%
  echo.
  echo **Generated:** %date% %time%
  echo.
  echo ## Steps
  echo ^| Step ^| Status ^| Details ^|
  echo ^|---^|---^|---^|
) > "%SNAPSHOT_FILE%"

REM ===== Log header =====
(
  echo verify_all.cmd started at %date% %time%
  echo Timestamp: %ts%
  echo Snapshot: %SNAPSHOT_FILE%
) > "%LOG_FILE%"

REM ===== Run =====
call :run_cmd "1. Stack up" "docker compose up -d --build" || goto finalize
call :run_cmd "2.1 Migrations" "scripts\migrate.cmd" || goto finalize
call :run_cmd "2.2 Alembic core-api current" "docker compose exec -T core-api sh -lc ^"alembic -c app/alembic.ini current^"" || goto finalize
call :run_cmd "2.3 Alembic auth-host current" "docker compose exec -T auth-host sh -lc ^"alembic -c alembic.ini current^"" || goto finalize

call :check_endpoints "3. Health checks" ^
  "http://localhost/health" ^
  "http://localhost/api/core/health" ^
  "http://localhost/api/auth/health" ^
  "http://localhost/api/ai/health" ^
  "http://localhost/api/int/health" ^
  || goto finalize

call :check_endpoints "4. Metrics checks" ^
  "http://localhost/metrics" ^
  "http://localhost:8001/metrics" ^
  "http://localhost:8010/metrics" ^
  || goto finalize

call :run_smoke_scripts || goto finalize
call :run_pytest_subset || goto finalize

goto finalize


REM ===== Helpers =====

:run_cmd
set "step=%~1"
set "cmdline=%~2"

>> "%LOG_FILE%" echo.
>> "%LOG_FILE%" echo [%step%] %cmdline%

REM Execute safely via CALL so quoted strings work
call %cmdline% >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :mark_fail "%step%" "%cmdline%"
  exit /b 1
) else (
  call :mark_ok "%step%" "%cmdline%"
  exit /b 0
)

:check_endpoints
set "step=%~1"
shift /1

set "failed=0"
:check_loop
if "%~1"=="" goto check_done
set "url=%~1"

>> "%LOG_FILE%" echo [%step%] Checking %url%
curl -fsS "%url%" >NUL 2>> "%LOG_FILE%"
if errorlevel 1 (
  set "failed=1"
  call :append_error "Endpoint failed: %url%"
)
shift /1
goto check_loop

:check_done
if "%failed%"=="0" (
  call :mark_ok "%step%" "All endpoints OK"
  exit /b 0
)
call :mark_fail "%step%" "One or more endpoints failed"
exit /b 1

:run_smoke_scripts
set "step=5. Smoke scripts"
set "failed=0"

call :run_cmd "5.1 auth-host tests subset" "docker compose exec -T auth-host pytest app/tests/test_health.py app/tests/test_metrics.py -q" || set "failed=1"
call :run_script_if_exists "scripts\billing_smoke.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_billing_finance.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_invoice_state_machine.cmd" || set "failed=1"

if "%failed%"=="0" (
  call :mark_ok "%step%" "All smoke scripts OK"
  exit /b 0
)
call :mark_fail "%step%" "One or more smoke scripts missing or failed"
exit /b 1

:run_script_if_exists
set "script=%~1"
if not exist "%script%" (
  call :append_error "Missing smoke script: %script%"
  exit /b 1
)
call :run_cmd "5.x %script%" "%script%"
exit /b %errorlevel%

:run_pytest_subset
set "step=6. Pytest smoke subset"

call :run_cmd "6.1 core tests subset" "docker compose exec -T core-api sh -lc ""pytest app/tests/test_transactions_pipeline.py app/tests/test_invoice_state_machine.py app/tests/test_settlement_v1.py app/tests/test_reconciliation_v1.py app/tests/test_documents_lifecycle.py""" || exit /b 1
call :run_cmd "6.2 integration-hub webhooks" "docker compose exec -T integration-hub sh -lc ""pytest neft_integration_hub/tests/test_webhooks.py""" || exit /b 1

call :mark_ok "%step%" "All pytest checks OK"
exit /b 0

:mark_ok
set "step=%~1"
set "details=%~2"
>> "%SNAPSHOT_FILE%" echo ^| %step% ^| OK ^| %details% ^|
exit /b 0

:mark_fail
set "step=%~1"
set "details=%~2"
>> "%SNAPSHOT_FILE%" echo ^| %step% ^| FAIL ^| %details% ^|
call :append_error "%step% failed: %details%"
exit /b 1

:append_error
>> "%ERROR_FILE%" echo - %~1
exit /b 0

:finalize
>> "%SNAPSHOT_FILE%" echo.
>> "%SNAPSHOT_FILE%" echo ## Errors
if exist "%ERROR_FILE%" (
  type "%ERROR_FILE%" >> "%SNAPSHOT_FILE%"
) else (
  >> "%SNAPSHOT_FILE%" echo - None
)

if exist "%ERROR_FILE%" (
  >> "%LOG_FILE%" echo verify_all.cmd finished with errors at %date% %time%
  exit /b 1
)

>> "%LOG_FILE%" echo verify_all.cmd finished OK at %date% %time%
exit /b 0

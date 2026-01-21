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

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

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
call :run_cmd "0.1 Local neft_shared/app.main import" "scripts\\dev_python_env.cmd" || goto finalize
call :run_cmd "0. Reset volumes" "docker compose down -v" || goto finalize
call :run_cmd "1. Stack up" "docker compose up -d --build" || goto finalize
call :run_cmd "1.0 Docker app.main import (core-api)" "docker compose exec -T core-api python -c ^\"import app.main; print('OK')^\"" || goto finalize
call :run_cmd "1.0.1 Docker neft_shared import (ai-service)" "docker run --rm neft-processing-ai-service python -c ^\"import neft_shared; print('OK')^\"" || goto finalize
call :run_cmd "1.0.2 Docker neft_shared import (workers)" "docker run --rm neft-processing-workers python -c ^\"import neft_shared; print('OK')^\"" || goto finalize
call :run_cmd "1.1 Alembic core-api upgrade head (clean DB)" "docker compose exec -T core-api sh -lc ^"alembic -c app/alembic.ini upgrade head^"" || goto finalize
call :run_cmd "2.0 Alembic core-api heads guard" "docker run --rm --network neft-processing_default neft-processing-core-api sh -lc ^"cd /app/app && alembic -c alembic.ini heads^"" || goto finalize
call :run_cmd "2.1 Migrations" "scripts\migrate.cmd" || goto finalize
call :run_cmd "2.2 Alembic core-api current" "docker compose exec -T core-api sh -lc ^"alembic -c app/alembic.ini current^"" || goto finalize
call :run_cmd "2.3 Alembic auth-host current" "docker compose exec -T auth-host sh -lc ^"alembic -c alembic.ini current^"" || goto finalize
call :run_cmd "2.4 partner-portal typecheck" "cd frontends\partner-portal && npm run typecheck" || goto finalize

call :wait_endpoint "%GATEWAY_BASE%%CORE_BASE%/health" 30 2
if errorlevel 1 (
  call :mark_fail "2.9 Wait core-api via gateway" "core-api not ready"
  goto finalize
) else (
  call :mark_ok "2.9 Wait core-api via gateway" "core-api ready"
)

call :run_cmd "2.9.1 Gateway core health" "curl -f %GATEWAY_BASE%%CORE_BASE%/health" || goto finalize
call :run_cmd "2.9.2 Core API internal health" "docker compose exec -T core-api sh -lc \"curl -f http://localhost:8000/health\"" || goto finalize

call :check_endpoints "3. Health checks" ^
  "%GATEWAY_BASE%/health" ^
  "%GATEWAY_BASE%%CORE_BASE%/health" ^
  "%GATEWAY_BASE%%AUTH_BASE%/health" ^
  "%GATEWAY_BASE%/api/ai/health" ^
  "%GATEWAY_BASE%/api/int/health" ^
  || goto finalize

call :check_endpoints "4. Metrics checks" ^
  "%GATEWAY_BASE%/metrics" ^
  "%GATEWAY_BASE%%CORE_BASE%/metrics" ^
  "http://localhost:8010/metrics" ^
  || goto finalize

call :run_cmd "4.1 core portal/me smoke" "curl -i %GATEWAY_BASE%%CORE_BASE%/portal/me" || goto finalize
call :run_cmd "4.2 auth-host jwks smoke" "curl -i http://localhost:8002/.well-known/jwks.json" || goto finalize
call :run_cmd "4.3 core openapi portal/me" "curl -s http://localhost:8001/api/openapi.json ^| findstr /I \"portal/me\"" || goto finalize

set "ADMIN_LOGIN_FILE=%TEMP%\\verify_admin_login_%RANDOM%.json"
call :run_cmd "4.4 admin login via gateway" "curl -sS -o \"%ADMIN_LOGIN_FILE%\" -H \"Content-Type: application/json\" -d \"{\\\"email\\\":\\\"admin@example.com\\\",\\\"password\\\":\\\"admin\\\"}\" %GATEWAY_BASE%%AUTH_BASE%/v1/auth/login" || goto finalize
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%T"
if "%ADMIN_TOKEN%"=="" (
  call :mark_fail "4.4 admin login via gateway" "No admin token returned"
  goto finalize
)
call :run_cmd "4.5 core portal/me (admin token)" "curl -f -H \"Authorization: Bearer %ADMIN_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/portal/me" || goto finalize
call :run_cmd "4.6 core v1 admin/me" "curl -f -H \"Authorization: Bearer %ADMIN_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/v1/admin/me" || goto finalize
call :check_not_401 "4.7 core legal/required (admin token)" "%GATEWAY_BASE%%CORE_BASE%/legal/required" "Authorization: Bearer %ADMIN_TOKEN%" || goto finalize

set "CLIENT_LOGIN_FILE=%TEMP%\\verify_client_login_%RANDOM%.json"
call :run_cmd "4.8 client login via gateway" "curl -sS -o \"%CLIENT_LOGIN_FILE%\" -H \"Content-Type: application/json\" -d \"{\\\"email\\\":\\\"client@neft.local\\\",\\\"password\\\":\\\"client\\\",\\\"portal\\\":\\\"client\\\"}\" %GATEWAY_BASE%%AUTH_BASE%/v1/auth/login" || goto finalize
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
if "%CLIENT_TOKEN%"=="" (
  call :mark_fail "4.8 client login via gateway" "No client token returned"
  goto finalize
)
call :run_cmd "4.9 core portal/me (client token)" "curl -f -H \"Authorization: Bearer %CLIENT_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/portal/me" || goto finalize
call :check_not_401 "4.10 core legal/required (client token)" "%GATEWAY_BASE%%CORE_BASE%/legal/required" "Authorization: Bearer %CLIENT_TOKEN%" || goto finalize

set "PARTNER_EMAIL=%NEFT_BOOTSTRAP_PARTNER_EMAIL%"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
set "PARTNER_PASSWORD=%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"

set "PARTNER_LOGIN_FILE=%TEMP%\\verify_partner_login_%RANDOM%.json"
call :run_cmd "4.11 partner login via gateway" "curl -sS -o \"%PARTNER_LOGIN_FILE%\" -H \"Content-Type: application/json\" -d \"{\\\"email\\\":\\\"%PARTNER_EMAIL%\\\",\\\"password\\\":\\\"%PARTNER_PASSWORD%\\\",\\\"portal\\\":\\\"partner\\\"}\" %GATEWAY_BASE%%AUTH_BASE%/v1/auth/login" || goto finalize
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%T"
if "%PARTNER_TOKEN%"=="" (
  call :mark_fail "4.11 partner login via gateway" "No partner token returned"
  goto finalize
)
call :run_cmd "4.12 auth /me (partner token)" "curl -f -H \"Authorization: Bearer %PARTNER_TOKEN%\" -H \"X-Portal: partner\" %GATEWAY_BASE%%AUTH_BASE%/v1/auth/me" || goto finalize
call :run_cmd "4.13 core portal/me (partner token)" "curl -f -H \"Authorization: Bearer %PARTNER_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/portal/me" || goto finalize
call :run_cmd "4.14 core partner/products (partner token)" "curl -f -H \"Authorization: Bearer %PARTNER_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/partner/products" || goto finalize
call :run_cmd "4.15 core partner/legal/profile (partner token)" "curl -f -H \"Authorization: Bearer %PARTNER_TOKEN%\" %GATEWAY_BASE%%CORE_BASE%/partner/legal/profile" || goto finalize

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
set "TMP_OUT=%TEMP%\verify_all_step_%RANDOM%.log"
call %cmdline% > "%TMP_OUT%" 2>&1
set "CMD_ERRORLEVEL=%ERRORLEVEL%"
type "%TMP_OUT%" >> "%LOG_FILE%"
set "SKIP_LINE="
for /f "usebackq delims=" %%L in (`findstr /c:"[SKIP]" "%TMP_OUT%"`) do if not defined SKIP_LINE set "SKIP_LINE=%%L"
if "%CMD_ERRORLEVEL%" NEQ "0" (
  call :mark_fail "%step%" "%cmdline%"
  exit /b 1
)
if defined SKIP_LINE (
  call :mark_skip "%step%" "%SKIP_LINE%"
  exit /b 0
)
call :mark_ok "%step%" "%cmdline%"
exit /b 0

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

:check_not_401
set "step=%~1"
set "url=%~2"
set "header=%~3"

for /f "usebackq delims=" %%S in (`curl -s -o NUL -w "%%{http_code}" -H "%header%" "%url%"`) do set "status=%%S"
if "%status%"=="401" (
  call :mark_fail "%step%" "Unauthorized (401) for %url%"
  exit /b 1
)
if "%status%"=="" (
  call :mark_fail "%step%" "No status for %url%"
  exit /b 1
)
if "%status%"=="000" (
  call :mark_fail "%step%" "Request failed for %url%"
  exit /b 1
)
call :mark_ok "%step%" "HTTP %status%"
exit /b 0

:run_smoke_scripts
set "step=5. Smoke scripts"
set "failed=0"

call :run_script_if_exists "scripts\smoke_gateway.cmd" || set "failed=1"
call :run_cmd "5.1 auth-host tests subset" "docker compose exec -T auth-host pytest app/tests/test_health.py app/tests/test_metrics.py -q" || set "failed=1"
call :run_script_if_exists "scripts\billing_smoke.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_billing_finance.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_admin_finance.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_admin_ops.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_invoice_state_machine.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_portal_unification_e2e.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_partner_core_e2e.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_partner_settlement_e2e.cmd" || set "failed=1"
call :run_script_if_exists "scripts\smoke_partner_trust_e2e.cmd" || set "failed=1"

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

:mark_skip
set "step=%~1"
set "details=%~2"
>> "%SNAPSHOT_FILE%" echo ^| %step% ^| SKIP ^| %details% ^|
exit /b 0

:append_error
>> "%ERROR_FILE%" echo - %~1
exit /b 0

:wait_endpoint
set "url=%~1"
set "retries=%~2"
set "delay=%~3"
set /a "attempt=1"

:wait_loop
>> "%LOG_FILE%" echo [wait_endpoint] Attempt !attempt!/%retries% %url%
curl -fsS "%url%" >NUL 2>> "%LOG_FILE%"
if errorlevel 1 (
  if !attempt! GEQ %retries% exit /b 1
  timeout /t %delay% /nobreak >NUL
  set /a "attempt+=1"
  goto wait_loop
)
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

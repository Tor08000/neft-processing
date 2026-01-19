@echo off
rem Smoke scenario: MoR correctness (gross=100, fee=15, penalties=5, net=80)
rem Runs the dedicated unit test that validates settlement breakdown, ledger, revenue, and payout gating.
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_mor_settlement_e2e"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "Running pytest platform/processing-core/app/tests/test_mor_settlement.py"

pytest platform/processing-core/app/tests/test_mor_settlement.py -q
if not "%ERRORLEVEL%"=="0" call :fail "pytest_failed"

call :log "SMOKE_MOR_SETTLEMENT: PASS"
echo SMOKE_MOR_SETTLEMENT: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "SMOKE_MOR_SETTLEMENT: FAIL at %FAILED_STEP%"
echo SMOKE_MOR_SETTLEMENT: FAIL at %FAILED_STEP%
exit /b 1

:log
set "LOG_MESSAGE=%~1"
echo %LOG_MESSAGE%
echo %LOG_MESSAGE%>>"%LOG_FILE%"
exit /b 0

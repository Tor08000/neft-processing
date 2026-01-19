@echo off
rem Smoke scenario: MoR production E2E (Happy path, Overdue recovery, Penalty path)
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_mor_e2e_prod"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"

call :log "Scenario A/C: MoR happy path + penalty (settlement snapshot, ledger, revenue, payout gating)"
pytest platform/processing-core/app/tests/test_mor_settlement.py -q
if not "%ERRORLEVEL%"=="0" call :fail "mor_settlement_tests_failed"

call :log "Scenario B: Overdue recovery (invoice overdue -> paid)"
pytest platform/processing-core/app/tests/integration/test_finance_negative_scenarios.py -k "scn2_overdue_then_paid" -q
if not "%ERRORLEVEL%"=="0" call :fail "overdue_recovery_tests_failed"

call :log "SMOKE_MOR_E2E_PROD: PASS"
echo SMOKE_MOR_E2E_PROD: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "SMOKE_MOR_E2E_PROD: FAIL at %FAILED_STEP%"
echo SMOKE_MOR_E2E_PROD: FAIL at %FAILED_STEP%
exit /b 1

:log
set "LOG_MESSAGE=%~1"
echo %LOG_MESSAGE%
echo %LOG_MESSAGE%>>"%LOG_FILE%"
exit /b 0

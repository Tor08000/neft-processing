@echo off
rem Smoke scenario: full MoR commerce + settlement + payout E2E
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_mor_e2e_full"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"

call :log "Step 1: Commerce overdue -> payment intake -> entitlements -> exports"
call "%~dp0smoke_billing_enforcement_unblock.cmd"
if not "%ERRORLEVEL%"=="0" call :fail "commerce_overdue_unblock_failed"

call :log "Step 2: MoR settlement snapshot/ledger/revenue/payout gating"
call "%~dp0smoke_mor_settlement_e2e.cmd"
if not "%ERRORLEVEL%"=="0" call :fail "mor_settlement_e2e_failed"

call :log "Step 3: Partner payout request -> approve"
call "%~dp0smoke_partner_settlement_e2e.cmd"
if not "%ERRORLEVEL%"=="0" call :fail "partner_payout_flow_failed"

call :log "SMOKE_MOR_E2E_FULL: PASS"
echo SMOKE_MOR_E2E_FULL: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "SMOKE_MOR_E2E_FULL: FAIL at %FAILED_STEP%"
echo SMOKE_MOR_E2E_FULL: FAIL at %FAILED_STEP%
exit /b 1

:log
set "LOG_MESSAGE=%~1"
echo %LOG_MESSAGE%
echo %LOG_MESSAGE%>>"%LOG_FILE%"
exit /b 0

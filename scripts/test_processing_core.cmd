@echo off
setlocal enabledelayedexpansion

REM ==========================================
REM Deprecated: use scripts\test_core_stack.cmd
REM ==========================================

echo [processing-core] Redirecting to scripts\test_core_stack.cmd
call scripts\test_core_stack.cmd %*
exit /b %errorlevel%

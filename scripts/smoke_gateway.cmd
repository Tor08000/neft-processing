@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BASE_URL=http://localhost"
set "FAILED=0"

call :check_head "%BASE_URL%/client/" "client portal"
call :check_head "%BASE_URL%/partner/" "partner portal"
call :check_head "%BASE_URL%/admin/" "admin portal"
call :check_head "%BASE_URL%/api/core/health" "core-api health"

if "%FAILED%"=="1" exit /b 1
echo Gateway smoke checks passed.
exit /b 0

:check_head
set "URL=%~1"
set "NAME=%~2"

echo Checking %NAME%: %URL%
curl -I "%URL%" | findstr /R /C:"HTTP/.* 200" >nul
if errorlevel 1 (
  echo Failed: %NAME%
  set "FAILED=1"
)
exit /b 0

@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"

call :check_portal admin
call :check_portal client
call :check_portal partner

echo All portal asset checks passed.
exit /b 0

:check_portal
set "PORTAL=%~1"
set "CSS_ASSET="
set "JS_ASSET="

echo.
echo Checking %PORTAL% portal...

curl -I "%BASE_URL%/%PORTAL%/" | findstr /I "200" >nul || exit /b 1

for /f "usebackq tokens=2 delims=\"" %%A in (`curl -s "%BASE_URL%/%PORTAL%/" ^| findstr /I "assets/index-.*\\.css"`) do (
  if not defined CSS_ASSET set "CSS_ASSET=%%A"
)

for /f "usebackq tokens=2 delims=\"" %%A in (`curl -s "%BASE_URL%/%PORTAL%/" ^| findstr /I "assets/index-.*\\.js"`) do (
  if not defined JS_ASSET set "JS_ASSET=%%A"
)

if not defined CSS_ASSET exit /b 1
if not defined JS_ASSET exit /b 1

curl -I "%BASE_URL%!CSS_ASSET!" | findstr /I "Content-Type: text/css" >nul || exit /b 1
curl -I "%BASE_URL%!JS_ASSET!" | findstr /I "Content-Type: application/javascript" >nul || exit /b 1

echo %PORTAL% CSS: %CSS_ASSET%
echo %PORTAL% JS: %JS_ASSET%
exit /b 0

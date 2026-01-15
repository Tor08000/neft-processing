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
set "HTML_FILE=%TEMP%\%PORTAL%_portal.html"

echo.
echo Checking %PORTAL% portal...

curl -I "%BASE_URL%/%PORTAL%/" | findstr /R /C:"HTTP/.* 200" >nul || exit /b 1

curl -s "%BASE_URL%/%PORTAL%/" > "%HTML_FILE%" || exit /b 1

for /f "usebackq tokens=1,* delims==" %%A in (`python scripts\extract_assets.py "%HTML_FILE%"`) do (
  if /I "%%A"=="css" set "CSS_ASSET=%%B"
  if /I "%%A"=="js" set "JS_ASSET=%%B"
)

if not defined CSS_ASSET exit /b 1
if not defined JS_ASSET exit /b 1

set "CSS_URL=!CSS_ASSET!"
if /I not "!CSS_ASSET:~0,4!"=="http" set "CSS_URL=%BASE_URL%!CSS_ASSET!"
set "JS_URL=!JS_ASSET!"
if /I not "!JS_ASSET:~0,4!"=="http" set "JS_URL=%BASE_URL%!JS_ASSET!"

curl -I "!CSS_URL!" | findstr /I "Content-Type: text/css" >nul || exit /b 1
curl -I "!JS_URL!" | findstr /I "Content-Type: application/javascript" >nul || exit /b 1

echo %PORTAL% CSS: %CSS_ASSET%
echo %PORTAL% JS: %JS_ASSET%
exit /b 0

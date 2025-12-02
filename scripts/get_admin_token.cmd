@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=admin123"
set "AUTH_ADMIN_URL=http://localhost/api/auth/api/v1/auth/login"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
        if /I "%%A"=="AUTH_ADMIN_URL" set "AUTH_ADMIN_URL=%%B"
        if /I "%%A"=="ADMIN_AUTH_URL" set "AUTH_ADMIN_URL=%%B"
    )
)

set "RESPONSE_FILE=%TEMP%\\admin_login_response.json"

echo Requesting admin token from %AUTH_ADMIN_URL% using %ADMIN_EMAIL%...
curl -s -S -X POST -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" "%AUTH_ADMIN_URL%" >"%RESPONSE_FILE%"
if errorlevel 1 (
    echo Failed to retrieve token.
    exit /b 1
)

set "RESPONSE="
set /p "RESPONSE="<"%RESPONSE_FILE%"
if not defined RESPONSE (
    echo Empty response received.
    exit /b 1
)

set "TOKEN="
set "MARK=\"access_token\":\""
set "AFTER=!RESPONSE:*%MARK%=!"
if "!AFTER!"=="!RESPONSE!" (
    echo access_token not found in response.
    exit /b 1
)
for /f "tokens=1 delims=,\"" %%A in ("!AFTER!") do set "TOKEN=%%A"

if not defined TOKEN (
    echo access_token not found in response.
    exit /b 1
)

echo !TOKEN! > ".admin_token"

echo Token saved to .admin_token and available as !TOKEN!.

endlocal & set "TOKEN=%TOKEN%"

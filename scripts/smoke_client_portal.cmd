@echo off
setlocal enabledelayedexpansion

if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" (
      if not "%%A:~0,1"=="#" set "%%A=%%B"
    )
  )
)

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_BASE_URL%"=="" set "AUTH_BASE_URL=%BASE_URL%"
if "%CORE_BASE_URL%"=="" set "CORE_BASE_URL=%BASE_URL%"

echo ^>^>^> client portal root
curl -sS -o "%TEMP%\client_portal.html" -w "%%{http_code}" "%BASE_URL%/client/" > "%TEMP%\client_portal.status"
set /p CLIENT_PORTAL_STATUS=<"%TEMP%\client_portal.status"
if not "%CLIENT_PORTAL_STATUS%"=="200" (
  echo client portal root failed (status=%CLIENT_PORTAL_STATUS%) 1>&2
  type "%TEMP%\client_portal.html" 1>&2
  exit /b 1
)
echo.

echo ^>^>^> client portal favicon
curl -sS -o "%TEMP%\client_favicon.svg" -w "%%{http_code}" "%BASE_URL%/client/brand/favicon.svg" > "%TEMP%\client_favicon.status"
set /p CLIENT_FAVICON_STATUS=<"%TEMP%\client_favicon.status"
if not "%CLIENT_FAVICON_STATUS%"=="200" (
  echo client portal favicon failed (status=%CLIENT_FAVICON_STATUS%) 1>&2
  type "%TEMP%\client_favicon.svg" 1>&2
  exit /b 1
)
echo.

echo ^>^>^> core health
curl -sS -o "%TEMP%\core_health.json" -w "%%{http_code}" "%CORE_BASE_URL%/api/core/health" > "%TEMP%\core_health.status"
set /p CORE_HEALTH_STATUS=<"%TEMP%\core_health.status"
if not "%CORE_HEALTH_STATUS%"=="200" (
  echo core health failed (status=%CORE_HEALTH_STATUS%) 1>&2
  type "%TEMP%\core_health.json" 1>&2
  exit /b 1
)
python -c "import json; data=json.load(open(r'%TEMP%\\core_health.json')); assert data.get('status') == 'ok', data"
if errorlevel 1 exit /b 1
echo.

echo ^>^>^> auth health
curl -sS -o "%TEMP%\auth_health.json" -w "%%{http_code}" "%AUTH_BASE_URL%/api/v1/auth/health" > "%TEMP%\auth_health.status"
set /p AUTH_HEALTH_STATUS=<"%TEMP%\auth_health.status"
if not "%AUTH_HEALTH_STATUS%"=="200" (
  echo auth health failed (status=%AUTH_HEALTH_STATUS%) 1>&2
  type "%TEMP%\auth_health.json" 1>&2
  exit /b 1
)
echo.

set "SMOKE_EMAIL=client_portal_smoke_%RANDOM%@example.com"
set "SMOKE_PASSWORD=ClientPortal123!"

echo ^>^>^> auth register
curl -sS -o "%TEMP%\auth_register.json" -w "%%{http_code}" -X POST "%AUTH_BASE_URL%/api/v1/auth/register" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"%SMOKE_EMAIL%\",\"password\":\"%SMOKE_PASSWORD%\",\"full_name\":\"Client Portal Smoke\"}" > "%TEMP%\auth_register.status"
set /p AUTH_REGISTER_STATUS=<"%TEMP%\auth_register.status"
if not "%AUTH_REGISTER_STATUS%"=="201" (
  echo auth register failed (status=%AUTH_REGISTER_STATUS%) 1>&2
  type "%TEMP%\auth_register.json" 1>&2
  exit /b 1
)
echo.

echo ^>^>^> auth login
curl -sS -o "%TEMP%\auth_login.json" -w "%%{http_code}" -X POST "%AUTH_BASE_URL%/api/v1/auth/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"%SMOKE_EMAIL%\",\"password\":\"%SMOKE_PASSWORD%\",\"portal\":\"client\"}" > "%TEMP%\auth_login.status"
set /p AUTH_LOGIN_STATUS=<"%TEMP%\auth_login.status"
if not "%AUTH_LOGIN_STATUS%"=="200" (
  echo auth login failed (status=%AUTH_LOGIN_STATUS%) 1>&2
  type "%TEMP%\auth_login.json" 1>&2
  exit /b 1
)

for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\auth_login.json')).get('access_token',''))"`) do set "AUTH_TOKEN=%%t"
if "%AUTH_TOKEN%"=="" (
  echo auth login missing token 1>&2
  type "%TEMP%\auth_login.json" 1>&2
  exit /b 1
)
echo.

echo ^>^>^> auth me
curl -sS -o "%TEMP%\auth_me.json" -w "%%{http_code}" "%AUTH_BASE_URL%/api/v1/auth/me" ^
  -H "Authorization: Bearer %AUTH_TOKEN%" > "%TEMP%\auth_me.status"
set /p AUTH_ME_STATUS=<"%TEMP%\auth_me.status"
if not "%AUTH_ME_STATUS%"=="200" (
  echo auth me failed (status=%AUTH_ME_STATUS%) 1>&2
  type "%TEMP%\auth_me.json" 1>&2
  exit /b 1
)
echo.

echo Client portal smoke checks passed.
endlocal
exit /b 0

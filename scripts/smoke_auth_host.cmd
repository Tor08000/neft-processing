@echo off
setlocal

if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" (
      if not "%%A:~0,1"=="#" set "%%A=%%B"
    )
  )
)

if "%AUTH_BASE_URL%"=="" set AUTH_BASE_URL=http://localhost:8000

if "%NEFT_BOOTSTRAP_ADMIN_EMAIL%"=="" set NEFT_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
if "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"=="" set NEFT_BOOTSTRAP_ADMIN_PASSWORD=admin
if "%NEFT_BOOTSTRAP_CLIENT_EMAIL%"=="" set NEFT_BOOTSTRAP_CLIENT_EMAIL=client@neft.local
if "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"=="" set NEFT_BOOTSTRAP_CLIENT_PASSWORD=client
if "%NEFT_BOOTSTRAP_PARTNER_EMAIL%"=="" set NEFT_BOOTSTRAP_PARTNER_EMAIL=partner@neft.local
if "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"=="" set NEFT_BOOTSTRAP_PARTNER_PASSWORD=partner

echo ^>^>^> auth health
curl -sS -o "%TEMP%\auth_health.json" -w "%%{http_code}" "%AUTH_BASE_URL%/api/auth/health" > "%TEMP%\auth_health.status"
set /p AUTH_HEALTH_STATUS=<"%TEMP%\auth_health.status"
if not "%AUTH_HEALTH_STATUS%"=="200" (
  echo auth health failed (status=%AUTH_HEALTH_STATUS%) 1>&2
  type "%TEMP%\auth_health.json" 1>&2
  exit /b 1
)
echo.

call :login admin "%NEFT_BOOTSTRAP_ADMIN_EMAIL%" "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"
call :login client "%NEFT_BOOTSTRAP_CLIENT_EMAIL%" "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"
call :login partner "%NEFT_BOOTSTRAP_PARTNER_EMAIL%" "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"

echo ^>^>^> public key
curl -sS -o "%TEMP%\auth_public_key.pem" -w "%%{http_code}" "%AUTH_BASE_URL%/api/v1/auth/public-key" > "%TEMP%\auth_public_key.status"
set /p AUTH_PUBLIC_STATUS=<"%TEMP%\auth_public_key.status"
if not "%AUTH_PUBLIC_STATUS%"=="200" (
  echo public key failed (status=%AUTH_PUBLIC_STATUS%) 1>&2
  type "%TEMP%\auth_public_key.pem" 1>&2
  exit /b 1
)
echo.

endlocal
exit /b 0

:login
setlocal
set LABEL=%~1
set EMAIL=%~2
set PASSWORD=%~3
echo ^>^>^> login %LABEL%
curl -sS -o "%TEMP%\auth_login.json" -w "%%{http_code}" -X POST "%AUTH_BASE_URL%/api/v1/auth/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}" > "%TEMP%\auth_login.status"
set /p LOGIN_STATUS=<"%TEMP%\auth_login.status"
if not "%LOGIN_STATUS%"=="200" (
  echo login %LABEL% failed (status=%LOGIN_STATUS%) 1>&2
  type "%TEMP%\auth_login.json" 1>&2
  endlocal & exit /b 1
)
echo.
endlocal & exit /b 0

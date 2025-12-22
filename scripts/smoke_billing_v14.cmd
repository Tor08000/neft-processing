@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "AUTH_URL=%BASE_URL%/api/auth/api/v1/auth/login"
set "CORE_URL=%BASE_URL%/api/core"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo [smoke] logging in as %ADMIN_EMAIL%
set "TOKEN="
for /f "usebackq tokens=*" %%t in (`powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $body=@{email='%ADMIN_EMAIL%';password='%ADMIN_PASSWORD%'}; $json=$body | ConvertTo-Json; $resp=Invoke-RestMethod -Method Post -Uri '%AUTH_URL%' -ContentType 'application/json' -Body $json; Write-Output $resp.access_token"`) do set "TOKEN=%%t"

if "%TOKEN%"=="" (
  echo [smoke][ERROR] failed to obtain token
  exit /b 1
)

set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

echo [smoke] core health
call :check "%CORE_URL%/health" 200 ""

echo [smoke] billing periods
call :check "%CORE_URL%/api/v1/admin/billing/periods" 200 "%AUTH_HEADER%"

set "RUN_PAYLOAD={^"period_type^":^"ADHOC^",^"start_at^":^"2024-01-01T00:00:00Z^",^"end_at^":^"2024-01-01T01:00:00Z^",^"tz^":^"UTC^"}"
echo [smoke] billing run
call :post "%CORE_URL%/api/v1/admin/billing/run" "!RUN_PAYLOAD!" 200 "%AUTH_HEADER%"

set "CLEARING_PAYLOAD={^"clearing_date^":^"2024-01-02^"}"
echo [smoke] clearing run
call :post "%CORE_URL%/api/v1/admin/clearing/run" "!CLEARING_PAYLOAD!" 200 "%AUTH_HEADER%"

echo [smoke] completed successfully
exit /b 0

:check
set "URL=%~1"
set "EXPECTED=%~2"
set "HEADER=%~3"
set "CODE="
if "%HEADER%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
)
if not "%CODE%"=="%EXPECTED%" (
  echo [smoke][ERROR] %URL% expected %EXPECTED% got %CODE%
  exit /b 1
)
exit /b 0

:post
set "URL=%~1"
set "BODY=%~2"
set "EXPECTED=%~3"
set "HEADER=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "Content-Type: application/json" -H "%HEADER%" -d "%BODY%" "%URL%"`) do set "CODE=%%c"
if not "%CODE%"=="%EXPECTED%" (
  echo [smoke][ERROR] POST %URL% expected %EXPECTED% got %CODE%
  exit /b 1
)
exit /b 0

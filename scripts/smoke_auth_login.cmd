@echo off
setlocal enabledelayedexpansion

set "BASE_URL=%~1"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

set "AUTH_EMAIL=%AUTH_EMAIL%"
if "%AUTH_EMAIL%"=="" set "AUTH_EMAIL=admin@example.com"
set "AUTH_PASSWORD=%AUTH_PASSWORD%"
if "%AUTH_PASSWORD%"=="" set "AUTH_PASSWORD=admin"

echo.
echo === Auth login ===
for /f "delims=" %%A in ('
  curl -s -X POST %BASE_URL%/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"%AUTH_EMAIL%\",\"password\":\"%AUTH_PASSWORD%\"}" ^|
  powershell -NoProfile -Command "$input | ConvertFrom-Json | Select-Object -ExpandProperty access_token"
') do set "TOKEN=%%A"

if "%TOKEN%"=="" (
  echo Failed to получить access_token
  exit /b 1
)

echo Token acquired.
echo.
echo === Auth me ===
curl -s -o NUL -w "HTTP %%{http_code}\n" %BASE_URL%/api/auth/me -H "Authorization: Bearer %TOKEN%"

echo.
echo === Portal me ===
curl -s -o NUL -w "HTTP %%{http_code}\n" %BASE_URL%/api/core/portal/me -H "Authorization: Bearer %TOKEN%"

endlocal

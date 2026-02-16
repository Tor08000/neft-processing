@echo off
setlocal ENABLEDELAYEDEXPANSION

if "%BASE_URL%"=="" set BASE_URL=http://localhost
if "%PARTNER_LOGIN%"=="" set PARTNER_LOGIN=partner@neft.local
if "%PARTNER_PASSWORD%"=="" set PARTNER_PASSWORD=partner

for /f "usebackq delims=" %%T in (`curl -sS -X POST "%BASE_URL%/api/v1/auth/login" -H "Content-Type: application/json" -d "{\"login\":\"%PARTNER_LOGIN%\",\"password\":\"%PARTNER_PASSWORD%\",\"portal\":\"partner\"}" ^| jq -r ".access_token"`) do set TOKEN=%%T
if "%TOKEN%"=="" (
  echo Failed to acquire partner token
  exit /b 1
)

curl -sS -f "%BASE_URL%/api/core/partner/me" -H "Authorization: Bearer %TOKEN%" >nul || exit /b 1

for /f "usebackq delims=" %%L in (`curl -sS -f -X POST "%BASE_URL%/api/core/partner/locations" -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"title\":\"Smoke Location\",\"address\":\"Smoke Address\"}" ^| jq -r ".id"`) do set LOCATION_ID=%%L
if "%LOCATION_ID%"=="" (
  echo Location was not created
  exit /b 1
)

curl -sS -f "%BASE_URL%/api/core/partner/locations" -H "Authorization: Bearer %TOKEN%" | jq -e ".[] | select(.id == \"%LOCATION_ID%\")" >nul || exit /b 1

echo Partner smoke passed

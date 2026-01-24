@echo off
setlocal enabledelayedexpansion

set API_URL=http://localhost
set LOGIN_PAYLOAD={"email":"client@neft.local","password":"client","portal":"client"}
set TOKEN=

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$resp = Invoke-RestMethod -Method Post -Uri '%API_URL%/api/v1/auth/login' -ContentType 'application/json' -Body '%LOGIN_PAYLOAD%'; $resp.access_token"`) do set TOKEN=%%A

if "%TOKEN%"=="" (
  echo Failed to получить токен. Проверьте доступность API.
  exit /b 1
)

set RESPONSE_FILE=%TEMP%\portal_me.json
set HTTP_STATUS=
for /f "delims=" %%A in ('curl -s -w "HTTP_STATUS:%%{http_code}" -o "%RESPONSE_FILE%" -H "Authorization: Bearer %TOKEN%" %API_URL%/api/core/portal/me') do set HTTP_STATUS=%%A

for /f "tokens=2 delims=:" %%A in ("%HTTP_STATUS%") do set STATUS_CODE=%%A

if not "%STATUS_CODE%"=="200" (
  echo portal/me status: %STATUS_CODE%
  powershell -NoProfile -Command "try { $payload = Get-Content '%RESPONSE_FILE%' -Raw | ConvertFrom-Json; if ($payload.error_id) { Write-Host ('error_id: ' + $payload.error_id) } } catch { Write-Host 'Failed to parse error response.' }"
  exit /b 1
)

powershell -NoProfile -Command "$payload = Get-Content '%RESPONSE_FILE%' -Raw | ConvertFrom-Json; Write-Host ('access_state: ' + $payload.access_state); if ($payload.access_reason) { Write-Host ('access_reason: ' + $payload.access_reason) }"

del "%RESPONSE_FILE%" >nul 2>&1

endlocal

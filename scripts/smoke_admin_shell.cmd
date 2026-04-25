@echo off
setlocal EnableExtensions EnableDelayedExpansion

if not exist logs mkdir logs
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "RUN_TS=%%t"
set "LOG_FILE=logs\\smoke_admin_shell_%RUN_TS%.log"

set "BASE_URL=http://localhost"
if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /I "%%A"=="GATEWAY_BASE_URL" set "BASE_URL=%%B"
  )
)

set "FAILED=0"

call :log ">>> core health"
call :check_status "%BASE_URL%/api/core/health" "200"

call :log ">>> admin me without token"
call :check_status "%BASE_URL%/api/core/v1/admin/me" "401"

call :log ">>> admin token"
for /f "usebackq delims=" %%t in (`scripts\\get_admin_token.cmd`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  call :log "FAIL: admin token missing"
  set "FAILED=1"
) else (
  call :log "token ok"
)

if not "%ADMIN_TOKEN%"=="" (
  call :log ">>> admin me with token"
  set "ADMIN_ME_FILE=%TEMP%\\admin_me_%RUN_TS%.json"
  curl -sS -o "!ADMIN_ME_FILE!" -w "%%{http_code}" -H "Authorization: Bearer %ADMIN_TOKEN%" "%BASE_URL%/api/core/v1/admin/me" > "%TEMP%\\admin_me_%RUN_TS%.status"
  set /p ADMIN_ME_STATUS=<"%TEMP%\\admin_me_%RUN_TS%.status"
  if not "!ADMIN_ME_STATUS!"=="200" (
    call :log "FAIL: admin me status !ADMIN_ME_STATUS!"
    type "!ADMIN_ME_FILE!" >> "%LOG_FILE%"
    set "FAILED=1"
  ) else (
    findstr /C:"roles" "!ADMIN_ME_FILE!" >nul
    if errorlevel 1 (
      call :log "FAIL: roles missing in admin me response"
      type "!ADMIN_ME_FILE!" >> "%LOG_FILE%"
      set "FAILED=1"
    ) else (
      call :log "PASS: admin me has roles"
    )
  )
)

call :log ">>> admin portal"
call :check_status "%BASE_URL%/admin/" "200"

if "%FAILED%"=="1" (
  call :log "FAIL"
  exit /b 1
)

call :log "PASS"
exit /b 0

:check_status
set "URL=%~1"
set "EXPECTED=%~2"
curl -sS -o "%TEMP%\\admin_smoke_body.txt" -w "%%{http_code}" "%URL%" > "%TEMP%\\admin_smoke_status.txt"
set /p STATUS=<"%TEMP%\\admin_smoke_status.txt"
if not "%STATUS%"=="%EXPECTED%" (
  call :log "FAIL: %URL% status=%STATUS% expected=%EXPECTED%"
  type "%TEMP%\\admin_smoke_body.txt" >> "%LOG_FILE%"
  set "FAILED=1"
) else (
  call :log "PASS: %URL% status=%STATUS%"
)
exit /b 0

:log
set "LOG_MESSAGE=%~1"
echo(!LOG_MESSAGE!
>> "%LOG_FILE%" echo(!LOG_MESSAGE!
exit /b 0

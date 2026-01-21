@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
set "FAILED=0"

call :check_portal client || set "FAILED=1"
call :check_portal admin || set "FAILED=1"

call :login_portal client "client@neft.local" "client" || set "FAILED=1"
call :login_portal admin "admin@example.com" "admin" || set "FAILED=1"

if "%FAILED%"=="1" exit /b 1

echo verify_portals: PASS
exit /b 0

:check_portal
set "PORTAL=%~1"
set "INDEX_FILE=%TEMP%\%PORTAL%_index_%RANDOM%.html"
set "STATUS_FILE=%TEMP%\%PORTAL%_status_%RANDOM%.txt"

curl -sS -o "%INDEX_FILE%" -w "%%{http_code}" "%BASE_URL%/%PORTAL%/" > "%STATUS_FILE%"
if errorlevel 1 (
  echo [%PORTAL%] Failed to download index.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%PORTAL%] Unexpected status for index: %STATUS%
  type "%INDEX_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%A in (`python -c "import re; from pathlib import Path; data=Path(r'%INDEX_FILE%').read_text(encoding='utf-8',errors='ignore'); assets=re.findall(r'/%PORTAL%/assets/[^\"\']+\.(?:js|mjs|css)', data); seen=set(); [print(a) for a in assets if not (a in seen or seen.add(a))]"`) do (
  call :check_asset "%%A" || exit /b 1
)

exit /b 0

:check_asset
set "ASSET=%~1"
set "EXPECT=application/javascript"
if /I "%ASSET:~-4%"==".css" set "EXPECT=text/css"

set "HEADER_FILE=%TEMP%\asset_header_%RANDOM%.txt"

curl -sS -I "%BASE_URL%%ASSET%" > "%HEADER_FILE%"
if errorlevel 1 (
  echo Failed to fetch headers for %ASSET%
  exit /b 1
)

findstr /R /I "HTTP/.* 200" "%HEADER_FILE%" >nul || (
  echo Unexpected status for %ASSET%
  type "%HEADER_FILE%"
  exit /b 1
)

findstr /R /I "Content-Type: .*%EXPECT%" "%HEADER_FILE%" >nul || (
  echo Unexpected Content-Type for %ASSET% (expected %EXPECT%)
  type "%HEADER_FILE%"
  exit /b 1
)

findstr /I "text/html" "%HEADER_FILE%" >nul && (
  echo HTML response detected for %ASSET%
  exit /b 1
)

exit /b 0

:login_portal
set "PORTAL=%~1"
set "EMAIL=%~2"
set "PASSWORD=%~3"
set "LOGIN_FILE=%TEMP%\login_%PORTAL%_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\login_%PORTAL%_%RANDOM%.status"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}" "%BASE_URL%/api/auth/v1/auth/login" > "%STATUS_FILE%"
if errorlevel 1 (
  echo [%PORTAL%] Login request failed.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%PORTAL%] Login returned status %STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN=%%T"
if "%TOKEN%"=="" (
  echo [%PORTAL%] No access token returned.
  exit /b 1
)

call :check_api "%PORTAL% auth/me" "%BASE_URL%/api/auth/v1/auth/me" "Authorization: Bearer %TOKEN%" "X-Portal: %PORTAL%" || exit /b 1
call :check_api "%PORTAL% portal/me" "%BASE_URL%/api/core/portal/me" "Authorization: Bearer %TOKEN%" || exit /b 1
call :check_api "%PORTAL% legal/required" "%BASE_URL%/api/core/legal/required" "Authorization: Bearer %TOKEN%" || exit /b 1
call :try_legal_accept "%PORTAL%" "%TOKEN%"
exit /b 0

:check_api
set "LABEL=%~1"
set "URL=%~2"
set "HEADER1=%~3"
set "HEADER2=%~4"
set "OUT_FILE=%TEMP%\verify_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\verify_%RANDOM%.status"

if "%HEADER2%"=="" (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "%HEADER1%" "%URL%" > "%STATUS_FILE%"
) else (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "%HEADER1%" -H "%HEADER2%" "%URL%" > "%STATUS_FILE%"
)

if errorlevel 1 (
  echo [%LABEL%] Request failed.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%LABEL%] Unexpected status %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)

exit /b 0

:try_legal_accept
set "PORTAL=%~1"
set "TOKEN=%~2"
if not exist "scripts\smoke_legal_accept.py" exit /b 0

python scripts\smoke_legal_accept.py --base "%BASE_URL%/api/core" --token "%TOKEN%" >nul 2>nul
if errorlevel 1 (
  echo [%PORTAL%] WARN: legal accept check failed
)

exit /b 0

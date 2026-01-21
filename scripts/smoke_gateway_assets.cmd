@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

set "FAILED=0"

call :check_portal admin || set "FAILED=1"
call :check_portal client || set "FAILED=1"

if "%FAILED%"=="1" exit /b 1

echo Gateway asset routing OK.
exit /b 0

:check_portal
set "PORTAL=%~1"
set "INDEX_FILE=%TEMP%\\%PORTAL%_index_%RANDOM%.html"

curl -sS "%BASE_URL%/%PORTAL%/" -o "%INDEX_FILE%"
if errorlevel 1 (
  echo Failed to download %PORTAL% index.
  exit /b 1
)

for /f "usebackq delims=" %%A in (`python -c "import re; from pathlib import Path; data=Path(r'%INDEX_FILE%').read_text(encoding='utf-8',errors='ignore'); assets=re.findall(r'/%PORTAL%/assets/[^\"\\']+\\.(?:js|mjs|css)', data); seen=set(); [print(a) for a in assets if not (a in seen or seen.add(a))]"`) do (
  call :check_asset "%%A" || exit /b 1
)
exit /b 0

:check_asset
set "ASSET=%~1"
set "EXPECT=javascript"
if /I "%ASSET:~-4%"==".css" set "EXPECT=text/css"

echo Checking %ASSET%
set "HEADER_FILE=%TEMP%\\asset_header_%RANDOM%.txt"
curl -sS -I "%BASE_URL%%ASSET%" > "%HEADER_FILE%"
if errorlevel 1 (
  echo Failed to fetch headers for %ASSET%
  exit /b 1
)

findstr /R /I "HTTP/.* 200" "%HEADER_FILE%" >nul || (
  echo Unexpected status for %ASSET%
  exit /b 1
)

findstr /R /I "Content-Type: .*%EXPECT%" "%HEADER_FILE%" >nul || (
  echo Unexpected Content-Type for %ASSET%
  exit /b 1
)

findstr /I "text/html" "%HEADER_FILE%" >nul && (
  echo HTML response detected for %ASSET%
  exit /b 1
)

curl -sS "%BASE_URL%%ASSET%" | findstr /I "<html" >nul && (
  echo HTML body detected for %ASSET%
  exit /b 1
)

exit /b 0

@echo off
setlocal enabledelayedexpansion

REM ==========================================
REM Smoke: Legal Gate (requires running stack)
REM Prereqs:
REM  - docker compose up -d --build
REM  - core-api + auth-host reachable via gateway
REM  - admin credentials in .env (ADMIN_EMAIL/ADMIN_PASSWORD)
REM ==========================================

set "GATEWAY_URL=http://localhost"
set "CORE_API_BASE=%GATEWAY_URL%/api/core"
set "AUTH_API_BASE=%GATEWAY_URL%/api/auth"
set "ADMIN_TOKEN_FILE=.admin_token"
set "SUBJECT_TYPE=CLIENT"
set "SUBJECT_ID=client-1"

call scripts\get_admin_token.cmd
if errorlevel 1 exit /b 1

set "TOKEN="
set /p "TOKEN="<"%ADMIN_TOKEN_FILE%"
if not defined TOKEN (
    echo Failed to read admin token from %ADMIN_TOKEN_FILE%.
    exit /b 1
)

echo [Legal Gate] Checking core-api health...
curl -s -S "%CORE_API_BASE%/health" >nul
if errorlevel 1 exit /b 1

echo [Legal Gate] Checking protected endpoint (expect LEGAL_REQUIRED)...
for /f %%A in ('curl -s -o "%TEMP%\\legal_gate_resp.json" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%CORE_API_BASE%/legal/protected?subject_type=%SUBJECT_TYPE%&subject_id=%SUBJECT_ID%"') do set "STATUS=%%A"
if not "%STATUS%"=="428" (
    echo Expected 428, got %STATUS%.
    exit /b 1
)

echo [Legal Gate] Fetching required documents...
curl -s -S -H "Authorization: Bearer %TOKEN%" "%CORE_API_BASE%/legal/required?subject_type=%SUBJECT_TYPE%&subject_id=%SUBJECT_ID%" >"%TEMP%\\legal_required.json"
if errorlevel 1 exit /b 1

echo [Legal Gate] Accepting required documents...
curl -s -S -X POST -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"subject_type\":\"%SUBJECT_TYPE%\",\"subject_id\":\"%SUBJECT_ID%\",\"accept_all\":true}" "%CORE_API_BASE%/legal/accept" >nul
if errorlevel 1 exit /b 1

echo [Legal Gate] Re-checking protected endpoint (expect 200)...
for /f %%A in ('curl -s -o "%TEMP%\\legal_gate_ok.json" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%CORE_API_BASE%/legal/protected?subject_type=%SUBJECT_TYPE%&subject_id=%SUBJECT_ID%"') do set "STATUS=%%A"
if not "%STATUS%"=="200" (
    echo Expected 200, got %STATUS%.
    exit /b 1
)

echo [Legal Gate] OK
endlocal

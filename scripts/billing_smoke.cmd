@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ===== Billing smoke =====

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "CORE_BILLING=%GATEWAY_BASE%%CORE_BASE%/v1/admin/billing"

set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

echo Token acquired.

echo Listing billing periods...
call :fetch_json "%CORE_BILLING%/periods" "periods.json" "billing periods"
if errorlevel 2 exit /b 0
if errorlevel 1 exit /b 1

echo Starting manual billing run (ADHOC)...
call :post_json "%CORE_BILLING%/run" "billing_run.json" "{\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-01T23:59:59Z\",\"tz\":\"UTC\",\"client_id\":null}" "billing run"
if errorlevel 2 exit /b 0
if errorlevel 1 exit /b 1

echo Fetching invoices...
call :fetch_json "%CORE_BILLING%/invoices" "invoices.json" "invoices list"
if errorlevel 2 exit /b 0
if errorlevel 1 exit /b 1

if exist invoice_id.txt del invoice_id.txt
python -c "import json, pathlib; data=json.load(open('invoices.json')); items=data.get('items'); assert isinstance(items, list); pathlib.Path('invoice_id.txt').write_text(items[0].get('id','')) if items else None"
if errorlevel 1 (
  echo [FAIL] Invoices list JSON invalid or missing items[].
  exit /b 1
)
if exist invoice_id.txt set /p INVOICE_ID=<invoice_id.txt

if "%INVOICE_ID%"=="" (
  echo [SKIP] No invoices found to generate PDF for.
  exit /b 0
)

echo Enqueue PDF generation for !INVOICE_ID! ...
call :post_json "%CORE_BILLING%/invoices/!INVOICE_ID!/pdf" "pdf_enqueue.json" "" "invoice pdf enqueue"
if errorlevel 2 exit /b 0
if errorlevel 1 exit /b 1

echo Checking PDF status...
call :fetch_json "%CORE_BILLING%/invoices/!INVOICE_ID!/pdf" "pdf_status.json" "invoice pdf status"
if errorlevel 2 exit /b 0
if errorlevel 1 exit /b 1

echo ===== Done =====
endlocal
exit /b 0

:fetch_json
set "URL=%~1"
set "OUT=%~2"
set "LABEL=%~3"
set "CODE="
curl -s -D "%TEMP%\billing_smoke.hdr" -o "%OUT%" -w "%%{http_code}" -H "%AUTH_HEADER%" "%URL%" > "%TEMP%\billing_smoke.code"
set /p CODE=<"%TEMP%\billing_smoke.code"
if "%CODE:~0,1%"=="5" (
  echo [FAIL] %LABEL% returned %CODE%.
  exit /b 1
)
if not "%CODE%"=="200" (
  echo [SKIP] %LABEL% returned %CODE%.
  exit /b 2
)
type "%OUT%"
exit /b 0

:post_json
set "URL=%~1"
set "OUT=%~2"
set "BODY=%~3"
set "LABEL=%~4"
set "CODE="
if "%BODY%"=="" (
  curl -s -D "%TEMP%\billing_smoke.hdr" -o "%OUT%" -w "%%{http_code}" -H "%AUTH_HEADER%" -X POST "%URL%" > "%TEMP%\billing_smoke.code"
) else (
  curl -s -D "%TEMP%\billing_smoke.hdr" -o "%OUT%" -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%" > "%TEMP%\billing_smoke.code"
)
set /p CODE=<"%TEMP%\billing_smoke.code"
if "%CODE:~0,1%"=="5" (
  echo [FAIL] %LABEL% returned %CODE%.
  exit /b 1
)
if not "%CODE%"=="200" if not "%CODE%"=="201" if not "%CODE%"=="202" (
  echo [SKIP] %LABEL% returned %CODE%.
  exit /b 2
)
type "%OUT%"
exit /b 0

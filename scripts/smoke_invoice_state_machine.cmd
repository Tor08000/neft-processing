@echo off
setlocal

if "%BASE%"=="" set "BASE=http://localhost"
if "%CORE_PREFIX%"=="" set "CORE_PREFIX=/api/core"
if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=%BASE%"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%CORE_PREFIX%"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%/v1/auth"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=change-me"

set "TOKEN="
set "AUTH_HEADER="
set "INVOICE_ID="
set "TOTAL_WITH_TAX=0"
set "PARTIAL_AMOUNT="
set "REMAINING_AMOUNT="

echo [1/14] Fetch admin token...
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

call :check_get "[2/14] /auth/me" "%AUTH_URL%/me" "%AUTH_HEADER%" "200" || goto :fail
call :check_get "[3/14] Billing periods" "%CORE_URL%/billing/periods?limit=1" "%AUTH_HEADER%" "200" || goto :fail

echo [4/14] Generate draft invoice for transitions...
set "CODE="
set "INVOICE_ID="
set "CONTENT_TYPE="
set "GEN_BODY=%TEMP%\invoice_gen.json"
set "GEN_HDR=%TEMP%\invoice_gen.hdr"
set "GEN_CODE=%TEMP%\invoice_gen.code"
set "INVOICE_ID_FILE=%TEMP%\invoice_id.txt"
setlocal DisableDelayedExpansion
curl -s -D "%GEN_HDR%" -o "%GEN_BODY%" -w "%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "{\"period_from\":\"2024-01-01\",\"period_to\":\"2024-01-31\",\"status\":\"DRAFT\"}" -X POST "%CORE_URL%/billing/invoices/generate" > "%GEN_CODE%"
endlocal
set /p CODE=<"%GEN_CODE%"
if "%CODE%"=="202" goto :step4_check_type
echo [WARN] Generation returned %CODE%, will reuse existing invoice if present.
goto :step4_list
:step4_check_type
python -c "import re; h=open(r'%GEN_HDR%','r',encoding='utf-8',errors='ignore').read(); m=re.search(r'^content-type:\\s*([^;\\r\\n]+)', h, re.I|re.M); print(m.group(1).strip() if m else '')" > "%TEMP%\invoice_gen_content.txt"
set /p CONTENT_TYPE=<"%TEMP%\invoice_gen_content.txt"
if /i "%CONTENT_TYPE%"=="application/json" goto :step4_parse
echo [WARN] Generation returned Content-Type %CONTENT_TYPE%, will reuse existing invoice if present.
goto :step4_list
:step4_parse
python -c "import json; data=json.load(open(r'%GEN_BODY%')); ids=data.get('created_ids') or []; print(ids[0] if ids else '')" > "%INVOICE_ID_FILE%"
set /p INVOICE_ID=<"%INVOICE_ID_FILE%"
if not "%INVOICE_ID%"=="" goto :step4_done
goto :step4_list

:step4_list
echo [5/14] List invoices to obtain id...
set "POLL_ATTEMPT=0"
set "EMPTY_ATTEMPT=0"
:invoice_list_retry
set "CODE="
set "INVOICE_ID="
set "INVOICES_URL=%CORE_URL%/billing/invoices?limit=1&offset=0"
if "%INVOICES_URL%"=="" (
  echo [FAIL] Invoices list URL is empty. Check BASE/CORE_PREFIX/GATEWAY_BASE/CORE_BASE.
  goto :fail
)
curl -s -D "%TEMP%\invoice_list.hdr" -o "%TEMP%\invoices.json" -w "%{http_code}" -H "%AUTH_HEADER%" "%INVOICES_URL%" > "%TEMP%\invoice_list.code"
set /p CODE=<"%TEMP%\invoice_list.code"
if "%CODE%"=="202" goto :invoice_list_202
if not "%CODE%"=="200" goto :invoice_list_fail
python -c "import json; data=json.load(open(r'%TEMP%\\invoices.json')); items=data.get('items') or []; print(items[0]['id'] if items else '')" > "%INVOICE_ID_FILE%"
set /p INVOICE_ID=<"%INVOICE_ID_FILE%"
if "%INVOICE_ID%"=="" goto :invoice_list_empty
goto :step4_done

:invoice_list_202
set /a POLL_ATTEMPT+=1
if %POLL_ATTEMPT% GEQ 30 goto :invoice_list_timeout
echo [WARN] Invoices list returned 202, retrying in 2s (%POLL_ATTEMPT%/30)...
timeout /t 2 /nobreak >NUL
goto :invoice_list_retry

:invoice_list_empty
set /a EMPTY_ATTEMPT+=1
if %EMPTY_ATTEMPT% LEQ 5 goto :invoice_list_retry_wait
goto :invoice_list_fail_empty

:invoice_list_retry_wait
echo [WARN] Invoices list empty, retrying in 2s (%EMPTY_ATTEMPT%/5)...
timeout /t 2 /nobreak >NUL
goto :invoice_list_retry

:invoice_list_timeout
echo [FAIL] Invoices list still returns 202 after 30 attempts.
goto :fail

:invoice_list_fail
echo [FAIL] Invoices list returned %CODE%.
goto :fail

:invoice_list_fail_empty
echo [FAIL] Invoices list returned no items.
goto :fail

:step4_done
if "%INVOICE_ID%"=="" goto :step4_fail
goto :step4_continue

:step4_fail
echo [FAIL] Could not resolve invoice id.
goto :fail

:step4_continue

call :post_step "[6/14] Mark invoice ISSUED" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[7/14] Mark invoice SENT" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"SENT\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "" || goto :fail

echo [8/14] Fetch invoice totals...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoice_detail.json "%CORE_URL%/billing/invoices/%INVOICE_ID%"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Invoice detail returned %CODE%.
  goto :fail
)
python -c "import json; d=json.load(open('invoice_detail.json')); print(d.get('total_with_tax') or d.get('total_amount') or 0)" > invoice_total.txt
set /p TOTAL_WITH_TAX=<invoice_total.txt
python -c "import json; data=json.load(open('invoice_detail.json')); total=int(data.get('total_with_tax') or data.get('total_amount') or 0); partial=max(1,total//2) if total else 0; remaining=max(total-partial,0); print(str(partial) + ' ' + str(remaining))" > invoice_amounts.txt
for /f "usebackq tokens=1,2" %%p in ("invoice_amounts.txt") do (
  set "PARTIAL_AMOUNT=%%p"
  set "REMAINING_AMOUNT=%%q"
)
if "%PARTIAL_AMOUNT%"=="" set "PARTIAL_AMOUNT=1"
if "%REMAINING_AMOUNT%"=="" set "REMAINING_AMOUNT=1"
echo     total=%TOTAL_WITH_TAX%, partial=%PARTIAL_AMOUNT%, remaining=%REMAINING_AMOUNT%

call :post_step "[9/14] Apply partial payment" "%CORE_URL%/finance/payments" "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%PARTIAL_AMOUNT%,\"currency\":\"RUB\"}" "%AUTH_HEADER%" "201" "200" || goto :fail

call :post_step "[10/14] Apply final payment" "%CORE_URL%/finance/payments" "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%REMAINING_AMOUNT%,\"currency\":\"RUB\",\"idempotency_key\":\"smoke-final\"}" "%AUTH_HEADER%" "201" "200" || goto :fail

call :post_step "[11/14] Attempt forbidden rollback (PAID->ISSUED)" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\",\"reason\":\"forbidden\"}" "%AUTH_HEADER%" "409" "" || goto :fail

call :post_step "[12/14] Invoice PDF enqueue (best-effort)" "%CORE_URL%/billing/invoices/%INVOICE_ID%/pdf" "" "%AUTH_HEADER%" "200" "202" || echo [WARN] PDF enqueue skipped.

for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoice_final.json "%CORE_URL%/billing/invoices/%INVOICE_ID%"`) do set "CODE=%%c"
if "%CODE%"=="200" (
  echo [13/14] Final invoice state:
  python -c "import json; d=json.load(open('invoice_final.json')); print('status={0}; paid_at={1}; amount_due={2}; amount_paid={3}'.format(d.get('status'), d.get('paid_at'), d.get('amount_due'), d.get('amount_paid')))"
) else (
  echo [WARN] Could not fetch final invoice (%CODE%).
)

call :check_get "[14/14] Clearing batches" "%CORE_URL%/clearing/batches?limit=1" "%AUTH_HEADER%" "200" || echo [WARN] Clearing check skipped.

echo [SMOKE] Invoice state machine smoke completed.
exit /b 0

:check_get
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:post_step
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
set "ALT=%~6"
set "CODE="
if "%BODY%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -X POST "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
)
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
if not "%ALT%"=="" if "%CODE%"=="%ALT%" (
  echo [OK] %LABEL% (%CODE%)
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:fail
echo [SMOKE] Failed.
exit /b 1

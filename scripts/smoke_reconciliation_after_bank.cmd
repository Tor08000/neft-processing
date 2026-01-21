@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

set "TOKEN="
set "AUTH_HEADER="

if not exist fixtures\bank\statement.csv (
  echo [FAIL] Missing fixtures\bank\statement.csv
  exit /b 1
)

echo [1/5] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

python -c "import json; content=open('fixtures/bank/statement.csv','r',encoding='utf-8').read(); payload={\"bank_code\":\"TEST\",\"period_start\":\"2026-01-01T00:00:00+00:00\",\"period_end\":\"2026-01-31T00:00:00+00:00\",\"file_name\":\"statement.csv\",\"content_type\":\"text/csv\",\"content\":content}; open('bank_payload.json','w',encoding='utf-8').write(json.dumps(payload, ensure_ascii=False))"

if not exist bank_payload.json (
  echo [FAIL] Could not create bank_payload.json
  goto :fail
)

echo [2/5] Import bank statement...
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d @bank_payload.json -o bank_statement.json "%CORE_URL%/integrations/bank/statements/import"`) do set "CODE=%%c"
if not "%CODE%"=="201" (
  echo [FAIL] Import returned %CODE%.
  goto :fail
)

echo [3/5] List bank reconciliation runs...
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o bank_runs.json "%CORE_URL%/integrations/bank/reconciliation/runs"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Runs list returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%r in (`python -c "import json; data=json.load(open('bank_runs.json')); runs=data.get('runs') or []; print(runs[0]['id'] if runs else '')"`) do set "RUN_ID=%%r"
if "%RUN_ID%"=="" (
  echo [FAIL] No reconciliation run found.
  goto :fail
)

echo [4/5] Fetch reconciliation diffs...
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o bank_diffs.json "%CORE_URL%/integrations/bank/reconciliation/runs/%RUN_ID%/diffs"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Diffs list returned %CODE%.
  goto :fail
)

echo [5/5] Smoke completed.
exit /b 0

:fail
exit /b 1

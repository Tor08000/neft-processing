@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "TOKEN="
set "AUTH_HEADER="

if not exist fixtures\bank\statement.csv (
  echo [FAIL] Missing fixtures\bank\statement.csv
  exit /b 1
)

echo [1/4] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

python -c "import json; content=open('fixtures/bank/statement.csv','r',encoding='utf-8').read(); payload={\"bank_code\":\"TEST\",\"period_start\":\"2026-01-01T00:00:00+00:00\",\"period_end\":\"2026-01-31T00:00:00+00:00\",\"file_name\":\"statement.csv\",\"content_type\":\"text/csv\",\"content\":content}; open('bank_payload.json','w',encoding='utf-8').write(json.dumps(payload, ensure_ascii=False))"

if not exist bank_payload.json (
  echo [FAIL] Could not create bank_payload.json
  goto :fail
)

echo [2/4] Import bank statement...
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d @bank_payload.json -o bank_statement.json "%CORE_URL%/integrations/bank/statements/import"`) do set "CODE=%%c"
if not "%CODE%"=="201" (
  echo [FAIL] Import returned %CODE%.
  goto :fail
)

echo [3/4] List bank statements...
for /f "usebackq tokens=*" %%c in (`curl -s -o bank_statements.json -w "%%{http_code}" -H "%AUTH_HEADER%" "%CORE_URL%/integrations/bank/statements"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] List returned %CODE%.
  goto :fail
)

echo [4/4] Smoke completed.
exit /b 0

:fail
exit /b 1

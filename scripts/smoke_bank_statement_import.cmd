@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "AUTH_URL=%BASE_URL%/api/auth/api/v1/auth"
set "CORE_URL=%BASE_URL%/api/core/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

set "TOKEN="
set "AUTH_HEADER="

if not exist fixtures\bank\statement.csv (
  echo [FAIL] Missing fixtures\bank\statement.csv
  exit /b 1
)

echo [1/4] Login to auth-host...
curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{""email"":""%ADMIN_EMAIL%"",""password"":""%ADMIN_PASSWORD%""}" > login.json
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open('login.json')).get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned.
  goto :fail
)
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

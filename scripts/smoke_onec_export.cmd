@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%/v1/auth"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=change-me"

set "TOKEN="
set "AUTH_HEADER="
set "EXPORT_ID="

echo [1/5] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

echo [2/5] Create 1C export...
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "{""period_start"":""2026-01-01"",""period_end"":""2026-01-31"",""mapping_version"":""2026.01"",""seller_name"":""ООО НЕФТЬ"",""seller_inn"":""7700000000"",""seller_kpp"":""770001001""}" -o onec_export.json "%CORE_URL%/integrations/onec/export"`) do set "CODE=%%c"
if not "%CODE%"=="201" (
  echo [FAIL] Export creation returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; print(json.load(open('onec_export.json')).get('id',''))"`) do set "EXPORT_ID=%%i"
if "%EXPORT_ID%"=="" (
  echo [FAIL] Export id missing.
  goto :fail
)

echo [3/5] Download export...
for /f "usebackq tokens=*" %%c in (`curl -s -o onec_export.xml -w "%%{http_code}" -H "%AUTH_HEADER%" "%CORE_URL%/integrations/onec/exports/%EXPORT_ID%/download"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Export download returned %CODE%.
  goto :fail
)

echo [4/5] Check exported XML...
python -c "import sys; data=open('onec_export.xml','rb').read(); sys.exit(0 if b'<NEFTExchange' in data else 1)"
if not "%ERRORLEVEL%"=="0" (
  echo [FAIL] Exported XML missing root.
  goto :fail
)

echo [5/5] Smoke completed.
exit /b 0

:fail
exit /b 1

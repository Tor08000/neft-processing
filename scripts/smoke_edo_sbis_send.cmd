@echo off
setlocal enabledelayedexpansion

set BASE_URL=%BASE_URL%
if "%BASE_URL%"=="" set BASE_URL=http://localhost:8080

set ADMIN_TOKEN=%ADMIN_TOKEN%
if "%ADMIN_TOKEN%"=="" (
  echo ADMIN_TOKEN is required
  exit /b 1
)

set DOC_ID=%DOC_ID%
set SUBJECT_TYPE=%SUBJECT_TYPE%
set SUBJECT_ID=%SUBJECT_ID%
set COUNTERPARTY_ID=%COUNTERPARTY_ID%
set ACCOUNT_ID=%ACCOUNT_ID%
set DOC_KIND=%DOC_KIND%
set DEDUPE_KEY=%DEDUPE_KEY%

if "%DOC_ID%"=="" (
  echo DOC_ID is required
  exit /b 1
)

curl -s -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/send" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"document_registry_id\":\"%DOC_ID%\",\"subject_type\":\"%SUBJECT_TYPE%\",\"subject_id\":\"%SUBJECT_ID%\",\"counterparty_id\":\"%COUNTERPARTY_ID%\",\"document_kind\":\"%DOC_KIND%\",\"account_id\":\"%ACCOUNT_ID%\",\"dedupe_key\":\"%DEDUPE_KEY%\"}" ^
  > edo_send_response.json

type edo_send_response.json
echo PASS

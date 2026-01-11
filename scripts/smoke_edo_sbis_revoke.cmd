@echo off
setlocal enabledelayedexpansion

set BASE_URL=%BASE_URL%
if "%BASE_URL%"=="" set BASE_URL=http://localhost:8080

set ADMIN_TOKEN=%ADMIN_TOKEN%
if "%ADMIN_TOKEN%"=="" (
  echo ADMIN_TOKEN is required
  exit /b 1
)

set DOCUMENT_ID=%DOCUMENT_ID%
if "%DOCUMENT_ID%"=="" (
  echo DOCUMENT_ID is required
  exit /b 1
)

curl -s -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/%DOCUMENT_ID%/revoke" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" > edo_revoke.json

type edo_revoke.json
echo PASS

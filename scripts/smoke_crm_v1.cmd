@echo off
setlocal ENABLEDELAYEDEXPANSION

if "%AUTH_URL%"=="" set AUTH_URL=http://localhost:8080
if "%GATEWAY_URL%"=="" set GATEWAY_URL=http://localhost:8080
if "%ADMIN_EMAIL%"=="" set ADMIN_EMAIL=admin@example.com
if "%ADMIN_PASSWORD%"=="" set ADMIN_PASSWORD=admin

echo [1/6] Login admin and get token...
for /f "delims=" %%A in ('curl -s -X POST %AUTH_URL%/api/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}"') do set LOGIN_JSON=%%A
for /f "tokens=2 delims=:,}" %%A in ("%LOGIN_JSON%") do set TOKEN=%%~A
set TOKEN=%TOKEN:"=%

echo [2/6] Create pipeline...
curl -s -X POST %GATEWAY_URL%/api/v1/crm/pipelines -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"name\":\"Smoke Pipeline\"}"

echo [3/6] Create stage...
curl -s -X POST %GATEWAY_URL%/api/v1/crm/pipelines/%PIPELINE_ID%/stages -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"name\":\"Lead\",\"position\":1}"

echo [4/6] Create contact...
curl -s -X POST %GATEWAY_URL%/api/v1/crm/contacts -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"full_name\":\"Smoke Contact\",\"email\":\"smoke@example.com\"}"

echo [5/6] Create deal and add comment...
curl -s -X POST %GATEWAY_URL%/api/v1/crm/deals -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"pipeline_id\":\"%PIPELINE_ID%\",\"stage_id\":\"%STAGE_ID%\",\"title\":\"Smoke deal\"}"
curl -s -X POST %GATEWAY_URL%/api/v1/crm/comments -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"entity_type\":\"deal\",\"entity_id\":\"%DEAL_ID%\",\"body\":\"smoke\"}"

echo [6/6] List audit...
curl -s "%GATEWAY_URL%/api/v1/crm/audit?entity_type=deal&entity_id=%DEAL_ID%" -H "Authorization: Bearer %TOKEN%"

endlocal

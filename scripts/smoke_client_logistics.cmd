@echo off
setlocal EnableExtensions

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"

set "TMP_DIR=%~dp0_tmp\\smoke_client_logistics"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1
set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_URL=%CORE_API_BASE%%CORE_BASE%"
set "LOGIN_OUT=%TMP_DIR%\client_logistics_login.json"

if not "%CLIENT_TOKEN%"=="" goto token_ready
set "STATUS="
for /f "usebackq tokens=*" %%c in (`curl -sS -o "%LOGIN_OUT%" -w "%%{http_code}" -H "Content-Type: application/json" -X POST "%AUTH_URL%/login" -d "{\"email\":\"%CLIENT_EMAIL%\",\"password\":\"%CLIENT_PASSWORD%\",\"portal\":\"client\"}"`) do set "STATUS=%%c"
if not "%STATUS%"=="200" (
  echo [FAIL] login HTTP %STATUS%
  type "%LOGIN_OUT%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_OUT%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"

:token_ready

if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] missing CLIENT_TOKEN
  exit /b 1
)

call :check "fleet" "%CORE_URL%/client/logistics/fleet"
if errorlevel 1 exit /b 1
call :check "trips" "%CORE_URL%/client/logistics/trips"
if errorlevel 1 exit /b 1
call :check "fuel" "%CORE_URL%/client/logistics/fuel"
if errorlevel 1 exit /b 1
set "TRIP_CREATE_BODY=%TMP_DIR%\client_logistics_trip_create_payload.json"
set "TRIP_CREATE_OUT=%TMP_DIR%\client_logistics_trip-create.json"
python -c "import json; from pathlib import Path; from datetime import datetime, timezone, timedelta; now=datetime.now(timezone.utc).replace(microsecond=0); payload={'title':'Smoke logistics trip','origin':{'label':'Moscow','lat':55.75,'lon':37.61,'planned_at':now.isoformat()},'destination':{'label':'Tula','lat':54.2,'lon':37.62,'planned_at':(now+timedelta(hours=4)).isoformat()},'stops':[{'label':'Serpukhov','lat':54.92,'lon':37.41}],'meta':{'smoke':'client_logistics'}}; Path(r'%TRIP_CREATE_BODY%').write_text(json.dumps(payload), encoding='utf-8')"
if errorlevel 1 exit /b 1
call :post_json "trip-create" "%CORE_URL%/client/logistics/trips" "%TRIP_CREATE_BODY%" "201"
if errorlevel 1 exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TRIP_CREATE_OUT%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "TRIP_ID=%%T"
if "%TRIP_ID%"=="" (
  echo [FAIL] trip-create missing id
  type "%TRIP_CREATE_OUT%"
  exit /b 1
)
call :check "trip-detail-created" "%CORE_URL%/client/logistics/trips/%TRIP_ID%"
if errorlevel 1 exit /b 1
call :check "fuel-consumption" "%CORE_URL%/client/logistics/fuel/consumption?date_from=2020-01-01T00:00:00Z&date_to=2035-01-01T00:00:00Z&group_by=trip"
if errorlevel 1 exit /b 1
set "FUEL_CONSUMPTION_BODY=%TMP_DIR%\client_logistics_fuel_consumption_payload.json"
python -c "import json; from pathlib import Path; Path(r'%FUEL_CONSUMPTION_BODY%').write_text(json.dumps({'trip_id':'%TRIP_ID%','distance_km':180,'vehicle_kind':'truck'}), encoding='utf-8')"
if errorlevel 1 exit /b 1
call :post_json "fuel-consumption-write" "%CORE_URL%/client/logistics/fuel/consumption" "%FUEL_CONSUMPTION_BODY%" "200"
if errorlevel 1 exit /b 1
call :expect_status "trip-detail-missing" "%CORE_URL%/client/logistics/trips/missing-trip" "GET" "404"
if errorlevel 1 exit /b 1

python "%~dp0write_client_logistics_evidence.py" "%~dp0..\docs\diag\client-logistics-fuel-write-live-smoke-20260425.json" "%TRIP_CREATE_OUT%" "%TMP_DIR%\client_logistics_fuel-consumption-write.json" "%TMP_DIR%\client_logistics_fuel-consumption.json"
if errorlevel 1 exit /b 1

echo [PASS] smoke_client_logistics OK
exit /b 0

:check
set "LABEL=%~1"
set "URL=%~2"
set "OUT_FILE=%TMP_DIR%\client_logistics_%LABEL%.json"
set "STATUS="
for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %CLIENT_TOKEN%" "%URL%"`) do set "STATUS=%%c"
if not "%STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL% HTTP 200
exit /b 0

:expect_status
set "LABEL=%~1"
set "URL=%~2"
set "METHOD=%~3"
set "EXPECTED=%~4"
set "OUT_FILE=%TMP_DIR%\client_logistics_%LABEL%.json"
set "STATUS="
for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -X "%METHOD%" -H "Authorization: Bearer %CLIENT_TOKEN%" "%URL%"`) do set "STATUS=%%c"
if not "%STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %STATUS% expected %EXPECTED%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL% HTTP %EXPECTED%
exit /b 0

:post_json
set "LABEL=%~1"
set "URL=%~2"
set "BODY_FILE=%~3"
set "EXPECTED=%~4"
set "OUT_FILE=%TMP_DIR%\client_logistics_%LABEL%.json"
set "STATUS="
for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -X POST -H "Authorization: Bearer %CLIENT_TOKEN%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%"`) do set "STATUS=%%c"
if not "%STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %STATUS% expected %EXPECTED%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL% HTTP %EXPECTED%
exit /b 0

@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%INT_BASE%"=="" set "INT_BASE=/api/int"
if "%AI_BASE%"=="" set "AI_BASE=/api/ai"

if "%NEFT_BOOTSTRAP_ADMIN_EMAIL%"=="" (
  set "ADMIN_EMAIL=admin@neft.local"
) else (
  set "ADMIN_EMAIL=%NEFT_BOOTSTRAP_ADMIN_EMAIL%"
)
if "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"=="" (
  set "ADMIN_PASSWORD=Neft123!"
) else (
  set "ADMIN_PASSWORD=%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"
)

call :check_url "gateway health" "%GATEWAY_BASE%/health" || exit /b 1
call :check_url "core health via gateway" "%GATEWAY_BASE%%CORE_BASE%/health" || exit /b 1
call :check_url "auth health via gateway" "%GATEWAY_BASE%%AUTH_BASE%/health" || exit /b 1
call :check_url "integration health via gateway" "%GATEWAY_BASE%%INT_BASE%/health" || exit /b 1
call :check_url "ai health via gateway" "%GATEWAY_BASE%%AI_BASE%/health" || exit /b 1

call :check_url "gateway metrics" "%GATEWAY_BASE%/metrics" || exit /b 1
call :check_url "core metrics" "http://localhost:8001/metrics" || exit /b 1
call :check_url "auth metrics" "http://localhost:8002/api/v1/metrics" || exit /b 1
call :check_url "integration metrics" "http://localhost:8010/metrics" || exit /b 1
call :check_url "ai metrics" "http://localhost:8003/metrics" || exit /b 1
call :check_url "otel metrics" "http://localhost:9464/metrics" || exit /b 1

call :check_url "prometheus health" "http://localhost:9090/-/healthy" || exit /b 1
call :check_url "grafana health" "http://localhost:3000/api/health" || exit /b 1
call :check_url "loki readiness" "http://localhost:3100/ready" || exit /b 1

call :fetch_json "prometheus targets" "http://localhost:9090/api/v1/targets" "observability_prometheus_targets.json" || exit /b 1
set "PROM_TARGETS_FILE=%TEMP%\observability_prometheus_targets.json"
python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%PROM_TARGETS_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); data=payload.get('data') or {}; active=data.get('activeTargets') or []; jobs={}; [jobs.setdefault((target.get('labels') or {}).get('job'), []).append(target) for target in active]; required=['gateway','core-api','auth-host','ai-service','otel-collector','crm-service','logistics-service','document-service','celery-exporter']; missing=[job for job in required if job not in jobs]; down=[job for job, targets in jobs.items() if job in required and any((target.get('health') or '').lower()!='up' for target in targets)]; print('[observability] jobs=' + ','.join(sorted(jobs))); print('[observability] missing=' + ','.join(missing) if missing else '[observability] missing=none'); print('[observability] down=' + ','.join(down) if down else '[observability] down=none'); raise SystemExit(1 if missing or down else 0)" || exit /b 1

call :login admin "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" || exit /b 1
call set "ADMIN_TOKEN=%%admin_TOKEN%%"
call :fetch_json_auth "admin runtime summary" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/runtime/summary" "%ADMIN_TOKEN%" "observability_runtime_summary.json" || exit /b 1
set "RUNTIME_SUMMARY_FILE=%TEMP%\observability_runtime_summary.json"
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RUNTIME_SUMMARY_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); health=data.get('health') or {}; required=['core_api','auth_host','gateway','integration_hub','ai_service','prometheus','grafana','loki','otel_collector']; bad={key: health.get(key) for key in required if str(health.get(key)).upper()!='UP'}; print('[runtime-summary] ' + ', '.join(f'{key}={health.get(key)}' for key in required)); raise SystemExit(1 if bad else 0)" || exit /b 1

echo OBSERVABILITY_STACK: PASS
exit /b 0

:check_url
set "LABEL=%~1"
set "URL=%~2"
set "STATUS_FILE=%TEMP%\obs_status_%RANDOM%.txt"

curl -sS -o NUL -w "%%{http_code}" "%URL%" > "%STATUS_FILE%"
set /p RESP_STATUS=<"%STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  exit /b 1
)
echo [PASS] %LABEL%
exit /b 0

:fetch_json
set "LABEL=%~1"
set "URL=%~2"
set "FILE_NAME=%~3"
set "RESP_FILE=%TEMP%\%FILE_NAME%"
set "RESP_STATUS_FILE=%TEMP%\obs_json_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  type "%RESP_FILE%"
  exit /b 1
)
python -c "import json; from pathlib import Path; json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore'))" >NUL 2>&1
if errorlevel 1 (
  echo [FAIL] %LABEL% invalid JSON
  type "%RESP_FILE%"
  exit /b 1
)
echo [PASS] %LABEL%
exit /b 0

:fetch_json_auth
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "FILE_NAME=%~4"
set "RESP_FILE=%TEMP%\%FILE_NAME%"
set "RESP_STATUS_FILE=%TEMP%\obs_auth_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  type "%RESP_FILE%"
  exit /b 1
)
python -c "import json; from pathlib import Path; json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore'))" >NUL 2>&1
if errorlevel 1 (
  echo [FAIL] %LABEL% invalid JSON
  type "%RESP_FILE%"
  exit /b 1
)
echo [PASS] %LABEL%
exit /b 0

:login
set "LABEL=%~1"
set "EMAIL=%~2"
set "PASSWORD=%~3"
set "PORTAL=%~4"
set "LOGIN_FILE=%TEMP%\%LABEL%_obs_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\%LABEL%_obs_login_status_%RANDOM%.txt"

if "%PORTAL%"=="" (
  set "LOGIN_PAYLOAD={\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}"
) else (
  set "LOGIN_PAYLOAD={\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}"
)
curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "%LOGIN_PAYLOAD%" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  echo [FAIL] %LABEL% login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "%LABEL%_TOKEN=%%T"
call set "LOGIN_TOKEN=%%%LABEL%_TOKEN%%"
if "%LOGIN_TOKEN%"=="" (
  echo [FAIL] %LABEL% login missing access_token
  exit /b 1
)

echo [PASS] %LABEL% login OK
exit /b 0

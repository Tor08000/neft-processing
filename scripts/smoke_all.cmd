@echo off
setlocal EnableExtensions EnableDelayedExpansion

for /f "delims=" %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "GREEN=%ESC%[32m"
set "RED=%ESC%[31m"
set "YELLOW=%ESC%[33m"
set "RESET=%ESC%[0m"

set "OK=%GREEN%OK%RESET%"
set "FAIL=%RED%FAIL%RESET%"

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "CORE_API_URL=%GATEWAY_BASE%%CORE_BASE%"
set "GATEWAY_URL=%GATEWAY_BASE%"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "FLOWER_URL=http://localhost:5555"
set "GRAFANA_URL=http://localhost:3000"
set "PROMETHEUS_URL=http://localhost:9090"
set "JAEGER_URL=http://localhost:16686"
set "MINIO_URL=http://localhost:9000"

set "POSTGRES_CONTAINER=neft-processing-postgres-1"
set "CORE_CONTAINER=neft-processing-core-api-1"
set "GATEWAY_CONTAINER=neft-processing-gateway-1"
set "AUTH_CONTAINER=neft-processing-auth-host-1"
set "FLOWER_CONTAINER=neft-processing-flower-1"
set "PROMETHEUS_CONTAINER=neft-processing-prometheus-1"
set "GRAFANA_CONTAINER=neft-processing-grafana-1"
set "JAEGER_CONTAINER=neft-processing-jaeger-1"
set "MINIO_CONTAINER=neft-processing-minio-1"

set "FAILED=0"

call :check_http "Core API health" "%CORE_API_URL%/health" "%CORE_CONTAINER%"
call :check_http "Core API metrics" "%CORE_API_URL%/metrics" "%CORE_CONTAINER%"

call :check_http_head "Gateway root" "%GATEWAY_URL%/" "%GATEWAY_CONTAINER%"
call :check_http_head "Gateway core health" "%GATEWAY_URL%/api/core/health" "%GATEWAY_CONTAINER%"

call :check_http "Auth health" "%AUTH_URL%/health" "%AUTH_CONTAINER%"

call :check_http_head_any "Flower UI" "%FLOWER_URL%/" "%FLOWER_CONTAINER%" "200 301 302 401 403"

call :check_http_head "Grafana" "%GRAFANA_URL%/" "%GRAFANA_CONTAINER%"
call :check_http "Prometheus ready" "%PROMETHEUS_URL%/-/ready" "%PROMETHEUS_CONTAINER%"
call :check_prom_targets "Prometheus core-api target" "%PROMETHEUS_URL%/api/v1/targets" "%PROMETHEUS_CONTAINER%"
call :check_http_head "Jaeger" "%JAEGER_URL%/" "%JAEGER_CONTAINER%"

call :check_http "MinIO ready" "%MINIO_URL%/minio/health/ready" "%MINIO_CONTAINER%"

call :check_cmd "Postgres select 1" "docker exec %POSTGRES_CONTAINER% psql -U neft -d neft -c ""select 1""" "%POSTGRES_CONTAINER%"

call :check_cmd "Alembic heads" "docker exec %CORE_CONTAINER% alembic heads --verbose" "%CORE_CONTAINER%"
call :check_cmd "Alembic current" "docker exec %CORE_CONTAINER% alembic current -v" "%CORE_CONTAINER%"
call :check_cmd "Alembic version rows" "docker exec %POSTGRES_CONTAINER% psql -tA -c ""select version_num from processing_core.alembic_version_core""" "%POSTGRES_CONTAINER%"

if "%FAILED%"=="0" (
  echo %OK% smoke_all.cmd finished successfully
  exit /b 0
)

echo %FAIL% smoke_all.cmd finished with failures
exit /b 1

:check_http
set "name=%~1"
set "url=%~2"
set "container=%~3"
curl -fsS "%url%" >NUL 2>&1
if errorlevel 1 (
  call :mark_fail "%name%" "%container%"
  exit /b 0
)
call :mark_ok "%name%"
exit /b 0

:check_http_head
set "name=%~1"
set "url=%~2"
set "container=%~3"
for /f "delims=" %%H in ('curl -s -o NUL -w "%%{http_code}" -I "%url%"') do set "code=%%H"
if "%code%"=="" set "code=000"
if "%code%"=="000" (
  call :mark_fail "%name%" "%container%"
  exit /b 0
)
if not "%code:~0,1%"=="2" if not "%code:~0,1%"=="3" (
  call :mark_fail "%name% (status %code%)" "%container%"
  exit /b 0
)
call :mark_ok "%name%"
exit /b 0

:check_http_head_any
set "name=%~1"
set "url=%~2"
set "container=%~3"
set "allowed=%~4"
for /f "delims=" %%H in ('curl -s -o NUL -w "%%{http_code}" -I "%url%"') do set "code=%%H"
if "%code%"=="" set "code=000"
set "hit=0"
for %%A in (%allowed%) do (
  if "%%A"=="%code%" set "hit=1"
)
if "%hit%"=="0" (
  call :mark_fail "%name% (status %code%)" "%container%"
  exit /b 0
)
call :mark_ok "%name% (status %code%)"
exit /b 0

:check_prom_targets
set "name=%~1"
set "url=%~2"
set "container=%~3"
set "found=0"
for /f "delims=" %%L in ('curl -fsS "%url%" ^| findstr /i "\"job\":\"core-api\"" ^| findstr /i "\"health\":\"up\""') do set "found=1"
if "%found%"=="1" (
  call :mark_ok "%name%"
  exit /b 0
)
call :mark_fail "%name%" "%container%"
exit /b 0

:check_cmd
set "name=%~1"
set "cmd=%~2"
set "container=%~3"
%cmd% >NUL 2>&1
if errorlevel 1 (
  call :mark_fail "%name%" "%container%"
  exit /b 0
)
call :mark_ok "%name%"
exit /b 0

:mark_ok
set "name=%~1"
echo [%OK%] %name%
exit /b 0

:mark_fail
set "name=%~1"
set "container=%~2"
echo [%FAIL%] %name%
set "FAILED=1"
if not "%container%"=="" (
  echo %YELLOW%[logs]%RESET% %container% (last 200 lines)
  docker logs --tail 200 %container%
)
exit /b 0

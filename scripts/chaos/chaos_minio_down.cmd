@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"

set "DOC_URL=%CHAOS_DOC_URL%"
set "EDO_URL=%CHAOS_EDO_URL%"

if "%DOC_URL%"=="" set "DOC_URL=http://localhost/api/core/documents/health"
if "%EDO_URL%"=="" set "EDO_URL=http://localhost/api/core/health"

echo [chaos] stopping minio via %DC_CMD%
%DC_CMD% stop minio
if errorlevel 1 (
  echo [chaos][ERROR] failed to stop minio
  exit /b 1
)

timeout /t 5 /nobreak >NUL

echo [chaos] attempting document download endpoint (expect graceful error)
for /f "delims=" %%i in ('curl -s -o NUL -w "%%{http_code}" %DOC_URL%') do set "DOC_CODE=%%i"
if "%DOC_CODE%"=="" (
  echo [chaos][WARN] document endpoint not reachable
) else (
  echo [chaos] document endpoint HTTP %DOC_CODE%
)

echo [chaos] attempting EDO send endpoint (expect graceful error)
for /f "delims=" %%i in ('curl -s -o NUL -w "%%{http_code}" %EDO_URL%') do set "EDO_CODE=%%i"
if "%EDO_CODE%"=="" (
  echo [chaos][WARN] EDO endpoint not reachable
) else (
  echo [chaos] EDO endpoint HTTP %EDO_CODE%
)

echo [chaos] starting minio via %DC_CMD%
%DC_CMD% start minio
if errorlevel 1 (
  echo [chaos][ERROR] failed to start minio
  exit /b 1
)

timeout /t 10 /nobreak >NUL

echo [chaos] minio down scenario completed (verify retries succeed after recovery)
exit /b 0

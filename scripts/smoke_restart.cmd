@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"

echo [smoke] restarting core services via %DC_CMD%
%DC_CMD% restart auth-host core-api postgres redis minio workers beat
if errorlevel 1 (
  echo [smoke][ERROR] restart failed
  exit /b 1
)

timeout /t 10 /nobreak >NUL
call "%~dp0smoke_billing_v14.cmd"
exit /b %errorlevel%

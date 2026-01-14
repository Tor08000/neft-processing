@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"

if not "%~1"=="" set "BASE_URL=%~1"

docker compose build partner-web client-web || exit /b 1

docker compose up -d partner-web client-web gateway || exit /b 1

curl -I "%BASE_URL%/partner/" | findstr /I "200" >nul || exit /b 1
curl -I "%BASE_URL%/client/" | findstr /I "200" >nul || exit /b 1

echo Frontend build smoke check passed.
exit /b 0

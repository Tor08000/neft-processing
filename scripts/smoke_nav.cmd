@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"

curl -I "%BASE_URL%/client/" | findstr /I "200" >nul || exit /b 1
curl -I "%BASE_URL%/client/transactions" | findstr /I "200" >nul || exit /b 1

curl -I "%BASE_URL%/partner/" | findstr /I "200" >nul || exit /b 1
curl -I "%BASE_URL%/partner/transactions" | findstr /I "200" >nul || exit /b 1

echo Navigation smoke checks passed.
exit /b 0

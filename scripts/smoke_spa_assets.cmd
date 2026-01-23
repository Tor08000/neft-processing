@echo off
setlocal enabledelayedexpansion

set "BASE_URL=%~1"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

for %%A in (admin client partner) do (
  echo.
  echo === %%A assets ===
  for /f "delims=" %%L in ('curl -s %BASE_URL%/%%A/ ^| findstr /I "assets/index-"') do (
    for /f "tokens=2 delims=\"\" %%P in ("%%L") do (
      set "ASSET_PATH=%%P"
      if not "!ASSET_PATH!"=="" (
        echo Checking !ASSET_PATH!
        curl -s -o NUL -w "HTTP %%{http_code}\n" %BASE_URL%!ASSET_PATH!
      )
    )
  )
)

endlocal

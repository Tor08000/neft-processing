@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"

for %%A in (admin client partner) do (
  echo.
  echo === %%A assets ===
  for /f "delims=" %%L in ('curl -s %BASE_URL%/%%A/ ^| findstr /I "assets/index-"') do (
    for /f "tokens=2 delims=\"\" %%P in ("%%L") do (
      set "ASSET_PATH=%%P"
      if not "!ASSET_PATH!"=="" (
        echo Checking !ASSET_PATH!
        curl -I %BASE_URL%!ASSET_PATH! | findstr /I "Content-Type"
      )
    )
  )
)

echo.
echo === Auth login ===
curl -i -X POST %BASE_URL%/api/auth/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}" | findstr /I "HTTP/ Content-Type"

echo.
echo Checking missing asset responses...
for %%A in (admin client partner) do (
  curl -i %BASE_URL%/%%A/assets/THIS_SHOULD_404.css | findstr /I "HTTP/ Content-Type"
)

endlocal

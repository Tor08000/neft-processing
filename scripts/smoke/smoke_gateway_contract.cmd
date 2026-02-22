@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BASE_URL=%~1"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

set "ADMIN_EMAIL=%NEFT_BOOTSTRAP_ADMIN_EMAIL%"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
set "ADMIN_PASSWORD=%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "FAILED=0"
set "ADMIN_TOKEN="

echo [smoke] gateway contract against %BASE_URL%

call :expect_status "%BASE_URL%/health" "200" "gateway health"
call :expect_status "%BASE_URL%/api/core/health" "200" "core health through gateway"

call :expect_status "%BASE_URL%/api/core/admin/auth/verify" "401" "admin verify without token"
call :expect_status "%BASE_URL%/api/core/client/auth/verify" "401" "client verify without token"
call :expect_status "%BASE_URL%/api/core/partner/auth/verify" "401" "partner verify without token"

call :fetch_admin_token
if not "%ADMIN_TOKEN%"=="" (
  call :expect_auth_status "%BASE_URL%/api/core/admin/auth/verify" "200" "admin verify with token" "%ADMIN_TOKEN%"
) else (
  echo [warn] admin token not acquired; skipping positive 200 checks
)

call :expect_header_and_status_and_not_404 "%BASE_URL%/api/core/v1/client/me" "X-API-Deprecated: true" "401" "legacy client alias (/me)"
call :expect_header_and_status_and_not_404 "%BASE_URL%/api/core/v1/partner/me" "X-API-Deprecated: true" "401" "legacy partner alias (/me)"

call :expect_status "%BASE_URL%/api/core/client/me" "401" "client protected route without token"
call :expect_status "%BASE_URL%/api/core/partner/me" "401" "partner protected route without token"
call :expect_status "%BASE_URL%/api/core/v1/admin/me" "401" "admin protected route without token"

if "%FAILED%"=="1" (
  echo [smoke] FAILED
  exit /b 1
)

echo [smoke] PASSED
exit /b 0

:expect_status
set "URL=%~1"
set "STATUS=%~2"
set "NAME=%~3"
for /f %%S in ('curl -s -o NUL -w "%%{http_code}" "%URL%"') do set "CODE=%%S"
if not "!CODE!"=="%STATUS%" (
  echo [fail] %NAME% expected %STATUS%, got !CODE! (%URL%)
  set "FAILED=1"
) else (
  echo [ok] %NAME% (%STATUS%)
)
exit /b 0

:expect_auth_status
set "URL=%~1"
set "STATUS=%~2"
set "NAME=%~3"
set "TOKEN=%~4"
for /f %%S in ('curl -s -o NUL -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%"') do set "CODE=%%S"
if not "!CODE!"=="%STATUS%" (
  echo [fail] %NAME% expected %STATUS%, got !CODE! (%URL%)
  set "FAILED=1"
) else (
  echo [ok] %NAME% (%STATUS%)
)
exit /b 0

:expect_header_and_not_404
set "URL=%~1"
set "HEADER=%~2"
set "NAME=%~3"
set "TMP_HEADERS=%TEMP%\neft_smoke_headers_%RANDOM%.txt"
curl -s -D "%TMP_HEADERS%" -o NUL "%URL%" >NUL
findstr /I /C:"HTTP/1.1 404" "%TMP_HEADERS%" >NUL
if not errorlevel 1 (
  echo [fail] %NAME% returned 404 (%URL%)
  set "FAILED=1"
  del "%TMP_HEADERS%" >NUL 2>&1
  exit /b 0
)
findstr /I /C:"%HEADER%" "%TMP_HEADERS%" >NUL
if errorlevel 1 (
  echo [fail] %NAME% missing header %HEADER% (%URL%)
  set "FAILED=1"
) else (
  echo [ok] %NAME% deprecation header present
)
del "%TMP_HEADERS%" >NUL 2>&1
exit /b 0

:expect_header_and_status_and_not_404
set "URL=%~1"
set "HEADER=%~2"
set "STATUS=%~3"
set "NAME=%~4"
set "TMP_HEADERS=%TEMP%\neft_smoke_headers_%RANDOM%.txt"
curl -s -D "%TMP_HEADERS%" -o NUL "%URL%" >NUL
findstr /I /C:"HTTP/1.1 404" "%TMP_HEADERS%" >NUL
if not errorlevel 1 (
  echo [fail] %NAME% returned 404 (%URL%)
  set "FAILED=1"
  del "%TMP_HEADERS%" >NUL 2>&1
  exit /b 0
)
findstr /I /C:"HTTP/1.1 %STATUS%" "%TMP_HEADERS%" >NUL
if errorlevel 1 (
  echo [fail] %NAME% expected HTTP %STATUS% (%URL%)
  set "FAILED=1"
) else (
  echo [ok] %NAME% status %STATUS%
)
findstr /I /C:"%HEADER%" "%TMP_HEADERS%" >NUL
if errorlevel 1 (
  echo [fail] %NAME% missing header %HEADER% (%URL%)
  set "FAILED=1"
) else (
  echo [ok] %NAME% header present: %HEADER%
)
del "%TMP_HEADERS%" >NUL 2>&1
exit /b 0

:fetch_admin_token
set "TMP_LOGIN=%TEMP%\neft_smoke_login_%RANDOM%.json"
set "TMP_OUT=%TEMP%\neft_smoke_login_out_%RANDOM%.json"
>"%TMP_LOGIN%" echo {"email":"%ADMIN_EMAIL%","password":"%ADMIN_PASSWORD%"}
curl -s -H "Content-Type: application/json" -d @"%TMP_LOGIN%" "%BASE_URL%/api/v1/auth/login" > "%TMP_OUT%"
:token_parse
set "ADMIN_TOKEN="
set "LINE="
for /f "delims=" %%L in ('type "%TMP_OUT%" ^| findstr /I /C:"\"access_token\""') do (
  set "LINE=%%L"
)
if "%LINE%"=="" goto :token_done
rem Extract after "access_token":
for /f "tokens=2 delims=:" %%A in ("%LINE%") do set "REST=%%A"
rem Trim up to first comma (if any)
for /f "tokens=1 delims=," %%A in ("%REST%") do set "REST=%%A"
rem Remove quotes and spaces
set "REST=%REST:"=%"
set "REST=%REST: =%"
set "ADMIN_TOKEN=%REST%"
:token_done
set "ADMIN_TOKEN=%ADMIN_TOKEN: =%"
del "%TMP_LOGIN%" >NUL 2>&1
del "%TMP_OUT%" >NUL 2>&1
if "%ADMIN_TOKEN%"=="" (
  echo [warn] unable to parse access_token from /api/v1/auth/login
) else (
  echo [ok] acquired admin token
)
exit /b 0

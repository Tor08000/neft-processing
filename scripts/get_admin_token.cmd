@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=admin123"
set "ADMIN_AUTH_URL=http://localhost/api/auth/api/v1/auth/login"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
        if /I "%%A"=="ADMIN_AUTH_URL" set "ADMIN_AUTH_URL=%%B"
    )
)

echo Requesting admin token from %ADMIN_AUTH_URL% using %ADMIN_EMAIL%...

powershell -NoLogo -NoProfile -Command ^
    "$body = @{ email = '%ADMIN_EMAIL%'; password = '%ADMIN_PASSWORD%' } | ConvertTo-Json;" ^
    "$resp = Invoke-RestMethod -Method Post -ContentType 'application/json' -Body $body -Uri '%ADMIN_AUTH_URL%';" ^
    "if (-not $resp.access_token) { Write-Error 'access_token not found in response'; exit 1 };" ^
    "$token = $resp.access_token;" ^
    "Set-Content -Path '.\\.admin_token' -Value $token;" ^
    "Write-Output \"set TOKEN=$token\";" 

if errorlevel 1 (
    echo Failed to retrieve token.
    exit /b 1
)

for /f "usebackq tokens=* delims=" %%T in (".admin_token") do set "TOKEN=%%T"

echo Token saved to .admin_token and available as %%TOKEN%%.

goto :eof

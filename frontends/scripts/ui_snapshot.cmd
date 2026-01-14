@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

if not exist "playwright.config.ts" (
  echo ERROR: config not found: playwright.config.ts
  exit /b 2
)
if not exist "package.json" (
  echo ERROR: package.json not found
  exit /b 2
)

echo NODE:
where node
echo NPX:
where npx
echo PWD:
cd
echo PLAYWRIGHT CONFIG EXISTS:
dir /b playwright.config.ts
echo TESTDIR LIST:
dir /b e2e\tests\*.spec.ts

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Running UI snapshot Playwright tests...
call npm run ui:snapshot
set EXIT_CODE=%ERRORLEVEL%

echo UI snapshot artifacts: %OUTPUT_DIR%
echo UI snapshot report: %OUTPUT_DIR%\REPORT.md
endlocal & exit /b %EXIT_CODE%

@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo PWD:
cd
echo LIST TEST FILE:
dir /b e2e\tests\ui_snapshot.spec.ts
if not exist "e2e\tests\ui_snapshot.spec.ts" (
  echo ERROR: test file not found: e2e\tests\ui_snapshot.spec.ts
  exit /b 2
)
echo Running UI snapshot Playwright tests...
call npx playwright test "e2e\tests\ui_snapshot.spec.ts" --config "playwright.config.ts" --project=chromium --reporter=list
set EXIT_CODE=%ERRORLEVEL%

echo UI snapshot artifacts: %OUTPUT_DIR%
echo UI snapshot report: %OUTPUT_DIR%\REPORT.md
endlocal & exit /b %EXIT_CODE%

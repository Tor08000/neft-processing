@echo off
setlocal enabledelayedexpansion

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Running UI snapshot Playwright tests...
npx playwright test e2e/tests/ui_snapshot.spec.ts
set EXIT_CODE=%ERRORLEVEL%

echo UI snapshot artifacts: %OUTPUT_DIR%
echo UI snapshot report: %OUTPUT_DIR%\REPORT.md
exit /b %EXIT_CODE%

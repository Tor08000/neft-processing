@echo off
setlocal enabledelayedexpansion

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Running UI link crawl Playwright tests...
npx playwright test e2e/tests/ui_link_crawl.spec.ts
set EXIT_CODE=%ERRORLEVEL%

echo UI link crawl artifacts: %OUTPUT_DIR%
echo UI link crawl report: %OUTPUT_DIR%\LINK_REPORT.md
exit /b %EXIT_CODE%

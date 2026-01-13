@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Running UI snapshot Playwright tests...
call npx playwright test "e2e\tests\ui_snapshot.spec.ts" --config "playwright.config.ts"
set EXIT_CODE=%ERRORLEVEL%

echo UI snapshot artifacts: %OUTPUT_DIR%
echo UI snapshot report: %OUTPUT_DIR%\REPORT.md
endlocal & exit /b %EXIT_CODE%

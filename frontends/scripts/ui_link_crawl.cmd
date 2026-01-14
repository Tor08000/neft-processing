@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set RUN_ID=%%i
set UI_SNAPSHOT_RUN_ID=%RUN_ID%

set OUTPUT_DIR=%CD%\ui-audit\%RUN_ID%
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

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

echo Running UI link crawl Playwright tests...
call npm run ui:link-crawl
set EXIT_CODE=%ERRORLEVEL%

echo UI link crawl artifacts: %OUTPUT_DIR%
echo UI link crawl report: %OUTPUT_DIR%\LINK_REPORT.md
exit /b %EXIT_CODE%

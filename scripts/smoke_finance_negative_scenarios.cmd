@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_finance_negative_scenarios.ps1"
exit /b %ERRORLEVEL%

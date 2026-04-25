@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_client_active_e2e.ps1"
exit /b %ERRORLEVEL%

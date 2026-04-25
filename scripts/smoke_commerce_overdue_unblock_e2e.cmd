@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_commerce_overdue_unblock_e2e.ps1"
exit /b %ERRORLEVEL%

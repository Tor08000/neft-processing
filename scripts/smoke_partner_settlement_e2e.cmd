@echo off
setlocal EnableExtensions DisableDelayedExpansion

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_partner_settlement_e2e.ps1"
exit /b %ERRORLEVEL%

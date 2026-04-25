@echo off
setlocal EnableExtensions DisableDelayedExpansion

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_partner_legal_payout_e2e.ps1"
exit /b %ERRORLEVEL%

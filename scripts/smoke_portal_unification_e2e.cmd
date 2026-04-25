@echo off
setlocal EnableExtensions DisableDelayedExpansion

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_portal_unification_e2e.ps1"
exit /b %ERRORLEVEL%

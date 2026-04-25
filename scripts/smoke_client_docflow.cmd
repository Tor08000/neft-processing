@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_client_docflow.ps1" %*
exit /b %ERRORLEVEL%

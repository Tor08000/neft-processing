@echo off
setlocal EnableExtensions DisableDelayedExpansion

python "%~dp0smoke_marketplace_order_loop.py"
exit /b %ERRORLEVEL%

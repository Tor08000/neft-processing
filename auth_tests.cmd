@echo off
setlocal
set "PYTHONPATH=platform\auth-host;platform\auth-host\app;shared\python"
pytest platform\auth-host\app\tests -q
exit /b %ERRORLEVEL%

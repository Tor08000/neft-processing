@echo off
setlocal

echo [chaos] starting full chaos smoke
call "%~dp0chaos_postgres_restart.cmd"
if errorlevel 1 exit /b 1

call "%~dp0chaos_redis_flush.cmd"
if errorlevel 1 exit /b 1

call "%~dp0chaos_minio_down.cmd"
if errorlevel 1 exit /b 1

echo [chaos] all scenarios completed
exit /b 0

@echo off
set PYTHONPATH=services\auth-host;services\auth-host\app;shared\python
pytest services\auth-host\app\tests -q

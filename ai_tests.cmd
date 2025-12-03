@echo off
set PYTHONPATH=services\ai-service;services\ai-service\app;shared\python
pytest services\ai-service\app\tests -q

@echo off
set PYTHONPATH=platform\ai-services\risk-scorer;platform\ai-services\risk-scorer\app;shared\python
pytest platform\ai-services\risk-scorer\app\tests -q

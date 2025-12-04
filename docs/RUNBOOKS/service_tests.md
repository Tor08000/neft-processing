# Прогон тестов по сервисам

Запускайте тесты каждого сервиса отдельно с явным `PYTHONPATH`, чтобы сборка зависимостей была предсказуемой.

## core-api

```
run_tests.cmd
```

## admin-web

```
admin_tests.cmd
```

## auth-host

```
auth_tests.cmd
```

`auth_tests.cmd` выставляет `PYTHONPATH=platform\auth-host;platform\auth-host\app;shared\python` и запускает `pytest platform\auth-host\app\tests -q`.

## ai-service

```
ai_tests.cmd
```

`ai_tests.cmd` выставляет `PYTHONPATH=platform\ai-services\risk-scorer;platform\ai-services\risk-scorer\app;shared\python` и запускает `pytest platform\ai-services\risk-scorer\app\tests -q`.

## billing-clearing workers

```
python -m pytest platform\billing-clearing\app\tests
```

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

`auth_tests.cmd` выставляет `PYTHONPATH=services\auth-host;services\auth-host\app;shared\python` и запускает `pytest services\auth-host\app\tests -q`.

## ai-service

```
ai_tests.cmd
```

`ai_tests.cmd` выставляет `PYTHONPATH=services\ai-service;services\ai-service\app;shared\python` и запускает `pytest services\ai-service\app\tests -q`.

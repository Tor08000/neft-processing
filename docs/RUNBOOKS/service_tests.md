# Прогон тестов по сервисам

Запускайте тесты каждого сервиса внутри запущенных контейнеров через `docker compose exec`, чтобы не тянуть зависимости на хост (особенно на Windows/CMD).

> Перед запуском убедитесь, что стек поднят: `docker compose up -d --build`

## core-api

```
scripts\test_core_api.cmd
```

## auth-host

```
scripts\test_auth_host.cmd
```

Скрипт оборачивает `docker compose exec -T auth-host pytest -q`, поэтому не требует локального `PYTHONPATH`.

## ai-service

```
ai_tests.cmd
```

`ai_tests.cmd` выставляет `PYTHONPATH=platform\ai-services\risk-scorer;platform\ai-services\risk-scorer\app;shared\python` и запускает `pytest platform\ai-services\risk-scorer\app\tests -q`.

## Smoke (gateway + services)

Быстрый прогон канонических health-ручек (Variant A):

```
curl http://127.0.0.1/health
curl http://127.0.0.1/api/core/health
curl http://127.0.0.1/api/auth/health
curl http://127.0.0.1/api/ai/v1/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/api/v1/health
```

# NEFT Processing: архитектура и структура монорепозитория

Эта версия отражает целевую архитектуру из ТЗ: монорепозиторий `neft-processing` с несколькими сервисами и общей библиотекой.

## Сервисы и их ответственность
- **core-api** — основной процессинговый API: CRUD клиентов, операции (authorization/capture), журнал операций, интеграция с Celery и БД.
- **auth-host** — аутентификация и управление пользователями/клиентами, выдача JWT, валидация токенов.
- **ai-service** — вспомогательный сервис скоринга (мок-логика сейчас, готовность к замене на реальную модель).
- **workers** — Celery worker/beat для фоновых задач (пересчёт лимитов, плановые задачи, вызовы ai-service).
- **shared/python/neft_shared** — общая библиотека: базовые настройки, логирование, утилиты.
- **nginx** — точка входа (reverse proxy): `/api` → core-api, `/auth` → auth-host, `/ai` → ai-service, отдаёт статическую заглушку если upstream недоступен.
- **infra** — вспомогательные скрипты/настройки; **db** — локальные данные Postgres/backup.

## Стек по сервисам
- **Язык/база**: Python 3.11, PostgreSQL 16, Redis 7.
- **core-api**: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Celery 5, httpx/uvicorn.
- **auth-host**: FastAPI, SQLAlchemy 2.x, Alembic (при необходимости), JWT (PyJWT), Pydantic v2.
- **ai-service**: FastAPI, Pydantic v2; внутренняя провайдерная абстракция для скоринга.
- **workers**: Celery 5 (worker и beat), httpx для вызовов сервисов, общие настройки/логирование из `neft_shared`.
- **Общее**: Docker/Docker Compose для локального запуска, JSON-логирование через `neft_shared.logging_setup`.

## Целевая структура репозитория
```
.
├── docker-compose.yml          # единая оркестрация сервисов
├── .env.example                # шаблон переменных окружения
├── Makefile / run_tests.cmd    # вспомогательные команды
├── shared/python/neft_shared   # общая библиотека (settings, logging, utils)
├── services/
│   ├── core-api/               # главный API процессинга (FastAPI + Postgres + Celery)
│   ├── auth-host/              # сервис аутентификации (FastAPI + JWT + Postgres)
│   ├── ai-service/             # сервис скоринга (FastAPI)
│   └── workers/                # Celery worker и beat
├── nginx/                      # конфигурация и статические файлы gateway
├── docs/                       # документация, ADR, runbooks, API схемы
└── db/                         # данные/бэкапы Postgres для локальной разработки
```

## Потоки данных (укрупнённо)
1. Терминал вызывает `core-api` → `POST /api/v1/transactions/authorize`.
2. `core-api` пишет операцию в Postgres, отправляет задачу `ai.score_transaction` в Celery через Redis.
3. Worker вызывает `ai-service` для скоринга, логирует результат/при необходимости обновляет операцию.
4. Кеширование/брокер: Redis; долговременное хранение: Postgres.
5. Доступ извне — через Nginx на порту 80 (`/api`, `/auth`, `/ai`).

## Причины выбранного дизайна
- Монорепозиторий упрощает согласованность версий контрактов и общих библиотек.
- Разделение сервисов по ответственности облегчает горизонтальное масштабирование и замену компонентов (например, ai-service на ML-модель).
- Общая библиотека `neft_shared` обеспечивает единообразное логирование и конфигурацию.
- Celery позволяет вынести тяжёлые и плановые задачи из критического пути API.

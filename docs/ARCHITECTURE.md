# Архитектура NEFT Processing v1

## Обзор
NEFT Processing реализован как монорепозиторий с набором Python-сервисов и общими компонентами. Архитектура оптимизирована для локального старта через Docker Desktop (в том числе на Windows/CMD), масштабирования через микросервисы и повторного использования общей библиотеки.

### Ключевые технологии
- Python 3.11, FastAPI, Pydantic v2, Uvicorn
- SQLAlchemy 2.0, Alembic, psycopg[binary]
- Celery 5.3, Redis 7 (broker/backend + кэш)
- PostgreSQL 16 (DB-first моделирование)
- httpx, PyJWT
- Docker, docker-compose, nginx

## Сервисы

### core-api (Python / FastAPI)
Главный бизнес-сервис процессинга. Отвечает за health-check, CRUD клиентов и карт (stub), операции, авторизацию и подтверждение транзакций, вызовы Celery и httpx-запросы в ai-service.

Основные эндпоинты:
- `GET /api/v1/health`
- `GET|POST|PUT|DELETE /api/v1/clients*`
- CRUD карт (упрощённо, stub)
- `POST /api/v1/transactions/authorize`
- `POST /api/v1/transactions/{id}/capture`
- `GET|POST|PUT|DELETE /api/v1/operations*`

Технологии и особенности:
- FastAPI + SQLAlchemy 2.0 + Alembic
- Redis для кеша и фоновой работы
- Celery producer (отправка задач в workers)
- DB-first: PostgreSQL → SQLAlchemy

### auth-host (Python / FastAPI)
Сервис аутентификации и управления пользователями.

Эндпоинты:
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

Особенности: FastAPI, SQLAlchemy 2.0, JWT через PyJWT или fastapi-jwt-auth.

### ai-service (Python / FastAPI)
Вспомогательный скоринговый сервис.

Эндпоинты:
- `GET /api/v1/health`
- `POST /api/v1/score`

Имитация модели: генерирует `score: float` и `decision: "allow" | "review" | "deny"`.

### workers (Python / Celery)
Celery worker + beat для фоновых задач:
- `limits.recalculate_client_limits`
- `limits.apply_daily_limits` (beat schedule)
- `ai.score_transaction` (обращается в ai-service)
- будущие задачи: отчёты, рассылки, клиринг и т.д.

### shared/python/neft_shared
Общий модуль для всех сервисов:
- `settings.py` для загрузки конфигурации (.env)
- `logging_setup.py` для единого JSON-логгера
- `utils/uuid.py`, `utils/time.py`
- общие константы

### nginx
Фронтовой прокси, который маршрутизирует запросы:
- `/api/` → core-api
- `/auth/` → auth-host
- `/ai/` → ai-service
- при недоступности upstream отдаёт `_upstream_down.html`

### PostgreSQL + Redis
Инфраструктурные сервисы:
- PostgreSQL 16 (основное хранилище)
- Redis 7 (broker/backend для Celery и кеш)

## Структура репозитория
Монорепозиторий организован по сервисам с общей библиотекой:

```
neft-processing/
│  README.md
│  docker-compose.yml
│  .env.example
│  .gitignore
│  .dockerignore
│  Makefile
│
├── shared/
│   └── python/
│       └── neft_shared/
│           │   __init__.py
│           │   settings.py
│           │   logging_setup.py
│           └── utils/
│               │   __init__.py
│               │   uuid.py
│               └── time.py
│
├── services/
│   ├── core-api/
│   │   │  Dockerfile
│   │   │  pyproject.toml
│   │   └── app/
│   │        │  main.py
│   │        │  config.py
│   │        │  db.py
│   │        │  celery_client.py
│   │        │  deps.py
│   │        │  __init__.py
│   │        ├── models/
│   │        │     __init__.py
│   │        │     client.py
│   │        │     card.py
│   │        │     operation.py
│   │        │     user.py
│   │        ├── schemas/
│   │        │     __init__.py
│   │        │     client.py
│   │        │     operation.py
│   │        │     transaction.py
│   │        └── api/
│   │             └── routes/
│   │                  │  health.py
│   │                  │  clients.py
│   │                  │  transactions.py
│   │                  │  operations.py
│   │
│   ├── auth-host/
│   │   │  Dockerfile
│   │   │  pyproject.toml
│   │   └── app/
│   │        │  main.py
│   │        │  config.py
│   │        │  db.py
│   │        │  security.py
│   │        ├── models/
│   │        ├── schemas/
│   │        └── api/routes/auth.py
│   │
│   ├── ai-service/
│   │   │  Dockerfile
│   │   │  pyproject.toml
│   │   └── app/
│   │        │  main.py
│   │        │  config.py
│   │        │  model_provider.py
│   │        └── api/routes/score.py
│   │
│   └── workers/
│       │  Dockerfile
│       │  pyproject.toml
│       └── app/
│            │  celery_app.py
│            │  config.py
│            └── tasks/
│                 │  limits.py
│                 └── ai.py
│
└── nginx/
    │  nginx.conf
    └── html/
         └── _upstream_down.html
```

Структура компактна и легко расширяется (например, для добавления pricing-service или reporting-service) без усложнения запуска.

NEFT Processing — локальная среда: Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx.

Быстрый старт:
1) Скопировать .env.example -> .env (cp -n .env.example .env)
2) docker compose up -d --build

Проверка:
- Core API напрямую: http://localhost:8001/api/v1/health
- Через gateway: http://localhost/api/core/api/v1/health
- Admin UI (через gateway с нужным префиксом): http://localhost/admin/

### Админский токен для локальной разработки

1) Убедитесь, что в `.env` прописаны `ADMIN_EMAIL` и `ADMIN_PASSWORD` (по умолчанию `admin@example.com` / `admin123`).
2) Выполните в PowerShell/cmd: `scripts\get_admin_token.cmd`. Скрипт запросит `access_token` у auth-host через gateway (`/api/auth/api/v1/auth/login`), сохранит его в `.admin_token` и выведет команду `set TOKEN=...`.
3) Пример запроса к защищённой ручке через gateway:

```
call scripts\get_admin_token.cmd
curl -i "http://localhost/api/core/api/v1/admin/operations?limit=5" ^
  -H "Authorization: Bearer %TOKEN%"
```

### Admin Web — как зайти

* Запустить окружение:
  * `docker compose up -d --build`
* Открыть в браузере: `http://localhost/admin/` (или напрямую в контейнер admin-web: `http://localhost:4173/admin/`)
* В форме логина ввести:
  * Email: `admin@example.com`
  * Пароль: `admin`
* После входа:
 * Отобразится журнал операций с пагинацией.
  * Все запросы идут через gateway:
    * `/api/auth/api/v1/auth/login`
    * `/api/core/api/v1/admin/operations`

### Gateway (Nginx)

* Конфигурация: `services/gateway/nginx.conf` (прокси для `/admin/`, `/api/auth/`, `/api/core/`, `/api/ai/`, favicon и health).
* Dockerfile: `services/gateway/Dockerfile` (основан на `nginx:1.27-alpine`, копирует конфиг в контейнер и перенаправляет логи в stdout/stderr).
* Сборка и запуск:
  * `docker compose build gateway` — собрать образ с конфигом.
  * `docker compose up -d gateway` — поднять только gateway (или `docker compose up -d --build` для всей среды).
  * Альтернативно: `docker build -f services/gateway/Dockerfile -t neft-processing-gateway .`.

## Общий Python-пакет `neft_shared`

В каталоге `shared/python` расположен пакет с общими настройками и логированием.

### Локальная установка

Для разработки установите пакет в editable-режиме из корня репозитория:

```bash
pip install -e shared/python
```

### Использование в сервисах

Сервисы `core-api`, `auth-host`, `ai-service` и `workers` подключают пакет как локальную зависимость через `pyproject.toml` (запись `"neft_shared @ file:../../shared/python"`). При установке зависимостей сервисов из корня репозитория пакет будет подтянут автоматически, а импорты доступны в коде как `from neft_shared...`.

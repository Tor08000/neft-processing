# Диагностика и снапшоты NEFT Processing

В каталоге `docs/diag/` собраны инструменты и примеры для фиксации состояния локальной инсталляции NEFT Processing. Основной скрипт диагностики — `inspect_neft_repo.py` в корне репозитория (версия правил фиксируется в самом отчёте, сейчас используется v0.1.5).

## Запуск диагностического скрипта

1. **Подготовьте окружение.**
   - Скопируйте переменные: `cp -n .env.example .env`.
   - Убедитесь, что заданы `ADMIN_EMAIL` и `ADMIN_PASSWORD` (пароль хранится локально).
   - На Windows установите Docker Desktop и запустите демон; активируйте виртуальное окружение Python с установленным Alembic (`pip install -r services/core-api/requirements.txt`).
2. **Поднимите инфраструктуру (опционально, для health-check).**
   - `docker compose up -d --build` из корня репозитория.
   - Проверки health зависят от доступности адресов `http://localhost/admin/`, `http://localhost/api/auth/api/v1/health`, `http://localhost/api/core/api/v1/health`.
3. **Запустите диагностику.**
   - Базовый прогон:
     ```bash
     python inspect_neft_repo.py
     ```
   - С запуском pytest для ключевых сервисов:
     ```bash
     python inspect_neft_repo.py --run-tests
     ```
4. **Сохранение отчёта.**
   - По умолчанию файл создаётся в `docs/diag/neft_state_YYYYMMDD_HHMM.txt` (можно переопределить `--output`).
   - Примеры итоговых файлов: [`neft_state_2025-12-02.txt`](./neft_state_2025-12-02.txt), `neft_state_2025-12-03_v0.1.3.txt`.
5. **Передача результатов.**
   - Добавьте созданный отчёт в артефакты или вложения тикета/PR.

## Что проверяет скрипт

- Структуру ключевых директорий (`services/*`, `db/`, `infra/`, `docs/`).
- Git-состояние рабочей копии.
- Конфигурацию `docker compose` (список сервисов, включая observability: grafana, jaeger, otel-collector, prometheus).
- Наличие Alembic миграций и результат `alembic heads` для `services/core-api`.
- Базовые health-check запросы (админка, auth-host, core-api).
- Опциональный запуск `pytest` для `core-api`, `auth-host`, `ai-service`.

## Статусы в отчёте

- `[OK]` — проверка завершена успешно.
- `[WARN]` — есть расхождения с ожиданиями (например, отсутствует сервис из `docker-compose.yml`).
- `[SKIP]` — проверка пропущена из-за окружения разработчика (например, Docker CLI или Alembic недоступны, флаг `--run-tests` не передан).
- `[FAIL]` — ошибка репозитория или конфигурации (несколько Alembic head, синтаксическая ошибка `docker compose config`, упавший health-check при запущенных сервисах).

### Типичные ситуации

- Docker не установлен или демон не запущен → чек `docker compose` = `[SKIP]` с подсказкой о необходимости запустить Docker Desktop.
- Alembic не установлен/не в PATH → чек `alembic heads` = `[SKIP]` с подсказкой об активации виртуального окружения.
- Конфликт миграций или ошибка в файле `alembic` → `[FAIL] alembic heads` с выводом оригинальной ошибки.
- `--run-tests` не передан → чек `pytest` = `[SKIP]`.

При необходимости можно хранить дополнительные снапшоты в этом каталоге, именуя их по дате.

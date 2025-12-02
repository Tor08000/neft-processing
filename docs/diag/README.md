# Диагностика и снапшоты NEFT Processing

В каталоге `docs/diag/` собраны инструменты и примеры для фиксации состояния локальной инсталляции NEFT Processing.

## Как снять снапшот

1. **Обновите зависимости и окружение.**
   - Скопируйте переменные: `cp -n .env.example .env`.
   - Проверьте, что в `.env` заданы `ADMIN_EMAIL` и `ADMIN_PASSWORD` (пароль хранится локально, в инструкцию не включается).
2. **Поднимите инфраструктуру.**
   - Запустите: `docker compose up -d --build` из корня репозитория.
   - Убедитесь, что сервисы отвечают по `http://localhost/admin/`, `http://localhost/api/auth/api/v1/health` и `http://localhost/api/core/api/v1/health`.
3. **Запустите диагностику.**
   - Команда по умолчанию (без сетевых проверок):
     ```bash
     python docs/diag/inspect_neft_repo.py --skip-health
     ```
   - Полный прогон с health-check и pytest:
     ```bash
     python docs/diag/inspect_neft_repo.py --run-tests
     ```
4. **Сохраните отчёт.**
   - Скрипт создаст файл `docs/diag/neft_state_YYYYMMDD_HHMM.txt` (можно задать `--output`).
   - Пример итогового файла: [`neft_state_2025-12-02.txt`](./neft_state_2025-12-02.txt).
5. **Приложите отчёт в тикет/PR.**
   - Добавьте файл из `docs/diag/` в артефакты или вложения.

## Состав каталога

- `inspect_neft_repo.py` — основной скрипт диагностики, поддерживает запуск тестов и health-check.
- `neft_state_2025-12-02.txt` — пример отчёта, показывает ожидаемую структуру вывода.

При необходимости можно хранить дополнительные снапшоты в этом каталоге, именуя их по дате.

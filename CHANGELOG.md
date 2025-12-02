# Changelog

## v0.1.0-admin-ui-online

- Поднята локальная среда со всеми сервисами (Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx/Gateway).
- Админ-панель доступна по `http://localhost/admin/`, авторизация через переменные `ADMIN_EMAIL` и `ADMIN_PASSWORD`.
- API проходит базовые health-check проверки, стабильная работа подтверждена.
- Добавлен обновлённый набор диагностик и пример снапшота в `docs/diag/`.
- README дополнен инструкциями по локальному запуску, входу в админку и съёму снапшотов.

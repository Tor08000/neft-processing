# Auth-host

Auth-host теперь работает как thin-proxy над `core-api` для авторизации терминала.

## Среда

Сервис читает настройки из окружения:

- `CORE_API_URL` — базовый URL Core API (по умолчанию `http://core-api:8000/api/v1`).

## Маршруты

- `POST /api/v1/processing/terminal-auth` — принимает `merchant_id`, `terminal_id`, `client_id`, `card_id`, `amount`, `currency`,
  пробрасывает запрос в Core API и возвращает его ответ. В случае ошибок Core API сервис возвращает HTTP-статус и `detail`, которые пришли от Core API.

## Логирование

Запросы и ответы логируются с техническими полями (merchant_id, terminal_id, client_id и т. д.) без номера карты.

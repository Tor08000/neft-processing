# UI/gateway debug checklist

Цель: быстро понять, почему админка/клиент не открываются через gateway после `docker compose up -d --build`.

## 1. Базовые проверки gateway

```bash
curl -i http://localhost/health
curl -i http://localhost/metrics
docker compose logs --tail=200 gateway
```

Ожидаем: `HTTP/1.1 200 OK`, в логах нет 502/504.

## 2. SPA точки входа

```bash
curl -I http://localhost/admin/           # должен вернуть 200 text/html
curl -I http://localhost/client/          # должен вернуть 200 text/html
curl -I http://localhost/admin/brand/favicon.svg
curl -I http://localhost/client/brand/favicon.svg
```

Если тут 302/404 — смотрим `location /` и `location /admin/`/`/client/` в `gateway/nginx.conf`.

## 3. Ассеты Vite

```bash
curl -I http://localhost/admin/assets/    # 200 + Cache-Control immutable
curl -I http://localhost/client/assets/   # 200 + Cache-Control immutable
```

При 404 ассетов: проверяем `base` в `vite.config.ts` и что gateway проксирует `/admin/assets/`/`/client/assets/` в соответствующие контейнеры.

## 4. API прокси через gateway

```bash
curl -i http://localhost/api/v1/health
curl -i http://localhost/admin/api/v1/health
curl -i http://localhost/client/api/v1/auth/health || true
```

- `/api/v1/health` → core-api напрямую.
- `/admin/api/v1/*` → должно уходить в core-api (кроме auth).
- `/admin/api/v1/auth/*` и `/client/api/v1/auth/*` → должны уходить в auth-host.

Если видим HTML вместо JSON — запрос попал в SPA, значит не хватает location-блока в gateway.

## 5. Браузерная диагностика (если открыт UI)

- Network: что запрашивает браузер (`/admin/assets/...`, `/admin/api/v1/...`).
- Console: ошибки CORS/404 на JS/CSS.
- Проверить, что `VITE_API_BASE_URL` в собранном bundle указывает на gateway (не на `http://localhost` внутри контейнера).

## 6. Preload data URI (Chrome warning)

Источником предупреждения был ручной `<link rel="preload" href="/src/main.tsx" as="script">` в `frontends/admin-ui/index.html`.
Vite в production преобразовывал этот preload в data URI, из-за чего Chrome ругался на "preload data:... not used".
Тег удалён — entrypoint грузится только через `<script type="module" src="/src/main.tsx">`, без data URI preloading.

## 7. Быстрый сброс и повтор

```bash
docker compose down -v
docker compose up -d --build
docker compose ps
```

Повторяем пункты 1–4 до стабильного 200/JSON.

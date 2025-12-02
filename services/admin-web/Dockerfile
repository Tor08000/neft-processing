# ---------- Stage 1: build SPA ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 1) Берём package.json именно из подкаталога services/admin-web
COPY services/admin-web/package*.json ./
RUN npm install

# 2) Копируем исходники только из подкаталога services/admin-web
COPY services/admin-web/. .

# 3) Собираем фронт
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

# Используем СВОЙ конфиг admin-web (лежит в services/admin-web/nginx.conf в корне контекста)
COPY services/admin-web/nginx.conf /etc/nginx/nginx.conf

# Кладём собранную статику
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

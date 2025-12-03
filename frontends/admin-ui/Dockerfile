# ---------- Stage 1: build SPA ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 1) Берём package.json именно из подкаталога frontends/admin-ui
COPY frontends/admin-ui/package*.json ./
RUN npm install

# 2) Копируем исходники только из подкаталога frontends/admin-ui
COPY frontends/admin-ui/. .

# 3) Собираем фронт
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

# Используем СВОЙ конфиг admin-web (лежит в frontends/admin-ui/nginx.conf в корне контекста)
COPY frontends/admin-ui/nginx.conf /etc/nginx/nginx.conf

# Корень статики – /usr/share/nginx/html
RUN mkdir -p /usr/share/nginx/html

# Кладём собранный Vite-бандл прямо в корень
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

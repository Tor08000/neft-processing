# services/admin-web/Dockerfile

# ---------- build stage ----------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine

# Кладём собранную SPA в стандартный каталог nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Используем СВОЙ конфиг admin-web
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

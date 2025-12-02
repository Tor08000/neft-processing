# services/admin-web/Dockerfile

# --------- Этап сборки фронта ---------
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# --------- Этап nginx ---------
FROM nginx:1.27

# Кладём наш конфиг nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Статические файлы SPA
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

# ---------- Stage 1: build SPA ----------
FROM node:20-alpine AS builder

WORKDIR /app

COPY services/client-web/package*.json ./
RUN npm install

COPY services/client-web/. .

RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY services/client-web/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

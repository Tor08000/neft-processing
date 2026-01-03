# ---------- Stage 1: build SPA ----------
FROM node:20-alpine AS builder

WORKDIR /app/frontends/admin-ui

COPY frontends/admin-ui/package*.json ./
RUN npm ci

COPY frontends/admin-ui/ ./
COPY frontends/shared/ /app/frontends/shared/
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY frontends/admin-ui/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/frontends/admin-ui/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

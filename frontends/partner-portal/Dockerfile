# ---------- Stage 1: build SPA ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app

COPY frontends/partner-portal/package.json frontends/partner-portal/package-lock.json ./
RUN npm ci

COPY frontends/partner-portal/ ./
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY frontends/partner-portal/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

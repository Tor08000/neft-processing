# ---------- Stage 1: build SPA ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app/frontends/client-portal

COPY frontends/client-portal/package*.json ./
RUN npm ci
RUN mkdir -p /app/frontends && ln -sf /app/frontends/client-portal/node_modules /app/frontends/node_modules

COPY frontends/client-portal/ ./
COPY frontends/shared/ /app/frontends/shared/
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY frontends/client-portal/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/frontends/client-portal/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

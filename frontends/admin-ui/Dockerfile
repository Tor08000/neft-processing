# ---------- Stage 1: build SPA ----------
FROM node:20-alpine AS builder

WORKDIR /app/frontends/admin-ui

ARG VITE_API_BASE_URL=/api
ARG VITE_CORE_API_BASE=/api/core
ARG VITE_AUTH_API_BASE=/api/v1/auth
ARG VITE_AI_API_BASE=/api/ai
ARG VITE_PUBLIC_BASE=/admin/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_CORE_API_BASE=$VITE_CORE_API_BASE
ENV VITE_AUTH_API_BASE=$VITE_AUTH_API_BASE
ENV VITE_AI_API_BASE=$VITE_AI_API_BASE
ENV VITE_PUBLIC_BASE=$VITE_PUBLIC_BASE

COPY frontends/admin-ui/package*.json ./
RUN npm ci
RUN mkdir -p /app/frontends && ln -sf /app/frontends/admin-ui/node_modules /app/frontends/node_modules

COPY frontends/admin-ui/ ./
COPY frontends/shared/ /app/frontends/shared/
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY frontends/admin-ui/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/frontends/admin-ui/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

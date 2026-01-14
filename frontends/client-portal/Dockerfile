# ---------- Stage 1: build SPA ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app/frontends/client-portal

ARG VITE_API_BASE_URL=/api
ARG VITE_CORE_API_BASE=/api/core
ARG VITE_AUTH_API_BASE=/api/auth
ARG VITE_AI_API_BASE=/api/ai
ARG VITE_PUBLIC_BASE=/client/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_CORE_API_BASE=$VITE_CORE_API_BASE
ENV VITE_AUTH_API_BASE=$VITE_AUTH_API_BASE
ENV VITE_AI_API_BASE=$VITE_AI_API_BASE
ENV VITE_PUBLIC_BASE=$VITE_PUBLIC_BASE
ENV npm_config_optional=true
ENV npm_config_fund=false
ENV npm_config_audit=false

COPY frontends/client-portal/package.json frontends/client-portal/package-lock.json ./
RUN npm ci

COPY frontends/client-portal/ ./
COPY frontends/shared/ /app/frontends/shared/
RUN npm run build

# ---------- Stage 2: nginx + статические файлы ----------
FROM nginx:1.27-alpine

COPY frontends/client-portal/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/frontends/client-portal/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

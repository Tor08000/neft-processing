# ---------- Stage 1: build ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app

# deps (deterministic)
COPY frontends/partner-portal/package.json frontends/partner-portal/package-lock.json ./
RUN npm ci

# sources
COPY frontends/partner-portal/ ./

# ✅ shared brand (so ../../../shared/... resolves to /app/shared/...)
COPY frontends/shared/ /app/shared/

# build
RUN echo "PARTNER_PORTAL_DOCKERFILE_MARKER_777"
RUN npm run build

# ---------- Stage 2: nginx + static ----------
FROM nginx:1.27-alpine

COPY frontends/partner-portal/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

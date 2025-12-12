SHELL := /bin/bash

# Можно переопределить переменную в CI, если надо:
# DOCKER_COMPOSE="docker-compose"
DOCKER_COMPOSE ?= docker compose

PROJECT_NAME := neft-processing

.PHONY: up down restart ps build \
        logs logs-core logs-auth logs-workers logs-nginx logs-ai logs-db \
        shell-core shell-auth shell-workers shell-ai \
        migrate test test-core test-auth test-ai test-workers \
        health health-core health-auth health-ai smoke \
        clean-volumes clean-images

# ----------------------------------------
# БАЗОВЫЕ ОПЕРАЦИИ С СТЕКОМ
# ----------------------------------------

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

restart: down up

ps:
	$(DOCKER_COMPOSE) ps

build:
	$(DOCKER_COMPOSE) build

# ----------------------------------------
# ЛОГИ СЕРВИСОВ
# ----------------------------------------

logs:
	$(DOCKER_COMPOSE) logs -f

logs-core:
	$(DOCKER_COMPOSE) logs -f core-api

logs-auth:
	$(DOCKER_COMPOSE) logs -f auth-host

logs-workers:
	$(DOCKER_COMPOSE) logs -f workers

logs-ai:
	$(DOCKER_COMPOSE) logs -f ai-service

logs-nginx:
	$(DOCKER_COMPOSE) logs -f nginx

logs-db:
	$(DOCKER_COMPOSE) logs -f db

# ----------------------------------------
# SHELL ВНУТРИ КОНТЕЙНЕРОВ
# ----------------------------------------

shell-core:
	$(DOCKER_COMPOSE) exec core-api sh

shell-auth:
	$(DOCKER_COMPOSE) exec auth-host sh

shell-workers:
	$(DOCKER_COMPOSE) exec workers sh

shell-ai:
	$(DOCKER_COMPOSE) exec ai-service sh

# ----------------------------------------
# МИГРАЦИИ БД (core-api / Alembic)
# ----------------------------------------

migrate:
	$(DOCKER_COMPOSE) exec core-api alembic upgrade head

# ----------------------------------------
# ТЕСТЫ
# ----------------------------------------
# Вариант через pytest внутри контейнеров.
# Предполагается, что pytest уже в requirements.* сервисов.

test-core:
	$(DOCKER_COMPOSE) run --rm core-api pytest

test-auth:
	$(DOCKER_COMPOSE) run --rm auth-host pytest

test-ai:
	$(DOCKER_COMPOSE) run --rm ai-service pytest

test-workers:
	$(DOCKER_COMPOSE) run --rm workers pytest || true

# Запуск всех тестов по очереди
test: test-core test-auth test-ai

# ----------------------------------------
# HEALTH-CHECK'И ЧЕРЕЗ NGINX
# ----------------------------------------
# Требует запущенного стека (nginx + сервисы).

health:
        curl -s "http://localhost/api/v1/health" || echo "core-api health check failed"

health-core: health

# Если позже сделаем /api/v1/health у auth-host и ai-service через nginx —
# сюда можно будет добавить отдельные проверки:
health-auth:
	@echo "Auth-host health endpoint через nginx пока не определён"

health-ai:
        @echo "AI-service health endpoint через nginx пока не определён"

smoke:
        bash scripts/smoke_local.sh

# ----------------------------------------
# ЧИСТКА
# ----------------------------------------

clean-volumes:
	$(DOCKER_COMPOSE) down -v

clean-images:
	$(DOCKER_COMPOSE) down --rmi local
